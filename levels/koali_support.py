from __future__ import annotations

import os
import re
from pathlib import Path

from levelupdiag_core.commands import normalize_command, run_command
from levelupdiag_core.manifest import level_map, load_manifest
from levelupdiag_core.util import redact, tail_text

_MODULE_NOT_FOUND_RE = re.compile(
    r'''ModuleNotFoundError:\s+No module named ['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)['\"]'''
)
_REPORT_RE = re.compile(r"(?im)\breport=(?P<path>[^\r\n]+)")


def missing_python_modules(text: str) -> list[str]:
    return sorted({m.group("name") for m in _MODULE_NOT_FOUND_RE.finditer(text or "")})


def _timeout(cfg, level_id: str) -> int:
    manifest = load_manifest(Path(cfg["_tool_root"]))
    meta = level_map(manifest)[level_id]
    return int(meta.get("timeout_seconds") or cfg.get("execution", {}).get("default_timeout_seconds", 120))


def effective_env(cfg) -> dict[str, str]:
    env = dict(os.environ)
    configured = cfg.get("env", {})
    if isinstance(configured, dict):
        env.update({str(k): str(v) for k, v in configured.items()})
    return env


def referenced_command_paths(target: Path, argv: list[str]) -> list[Path]:
    """Return relative file arguments that the configured validator expects to exist."""
    paths: list[Path] = []
    for token in argv[1:]:
        if not token or token.startswith("-"):
            continue
        candidate = Path(token)
        if candidate.is_absolute():
            continue
        if candidate.suffix.casefold() not in {".py", ".json", ".toml", ".yaml", ".yml"}:
            continue
        paths.append(target / candidate)
    return paths


def referenced_gate_reports(cfg, output: str) -> list[dict]:
    """Read only explicitly referenced kOA-Linux gate reports inside the target repo."""
    target = Path(cfg["_target_root"]).resolve()
    koa = cfg.get("koa", {})
    directory_name = str(koa.get("gate_report_directory", "koa-ci-evidence")).casefold()
    suffix = str(koa.get("gate_report_suffix", "-gate-report.json")).casefold()
    limit = int(koa.get("gate_report_capture_kb", 128)) * 1024
    items: list[dict] = []
    seen: set[Path] = set()
    for match in _REPORT_RE.finditer(output or ""):
        raw = match.group("path").strip().strip('"').strip("'")
        if not raw:
            continue
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = target / p
        try:
            p = p.resolve(strict=False)
            if not p.is_relative_to(target) or p in seen or not p.is_file() or p.is_symlink():
                continue
        except (OSError, ValueError):
            continue
        parts = {part.casefold() for part in p.parts}
        if directory_name not in parts or not p.name.casefold().endswith(suffix):
            continue
        seen.add(p)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            items.append({"path": p.relative_to(target).as_posix(), "read_error": f"{type(exc).__name__}: {exc}"})
            continue
        if cfg.get("redaction", {}).get("enabled", True):
            text = redact(text, str(cfg.get("redaction", {}).get("replacement", "<REDACTED>")))
        items.append({"path": p.relative_to(target).as_posix(), "content_tail": tail_text(text, limit)})
    return items


def run_validation(
    cfg,
    report,
    *,
    command_key: str | None = None,
    command_override=None,
    required: bool,
    blocked_marker: str | None = None,
    include_gate_reports: bool = False,
    recommendation: str | None = None,
):
    target = Path(cfg["_target_root"])
    command = command_override if command_override is not None else cfg.get("commands", {}).get(command_key or "")
    if command in (None, "", []):
        verdict = "CONFIG_ERROR" if required else "SKIP"
        report.add(
            f"{report.level_id.lower()}.{command_key or 'command'}.missing",
            verdict,
            "configuration",
            f"Required kOA-Linux command '{command_key}' is not configured." if required else f"Optional kOA-Linux command '{command_key}' is not configured; level skipped.",
            recommendation=(f"Configure commands.{command_key} with the documented public kOA-Linux validator." if required else None),
        )
        return
    try:
        argv = normalize_command(command)
    except ValueError as exc:
        report.add(
            f"{report.level_id.lower()}.{command_key or 'command'}.invalid",
            "CONFIG_ERROR",
            "configuration",
            "Configured validation command cannot be parsed safely.",
            evidence=str(exc),
        )
        return

    missing_paths = [p for p in referenced_command_paths(target, argv) if not p.is_file()]
    if missing_paths:
        relative = []
        for p in missing_paths:
            try:
                relative.append(p.relative_to(target).as_posix())
            except ValueError:
                relative.append(str(p))
        report.add(
            f"{report.level_id.lower()}.{command_key or 'command'}.path",
            "CONFIG_ERROR",
            "configuration",
            "Configured kOA-Linux validation command references file(s) that do not exist under target_repo_root.",
            evidence={"target_repo_root": str(target), "missing_paths": relative, "argv": argv},
            recommendation="Verify target_repo_root and keep the validator paths aligned with the kOA-Linux repository documentation.",
        )
        return

    try:
        result = run_command(
            argv,
            cwd=target,
            timeout_seconds=_timeout(cfg, report.level_id),
            capture_limit_kb=int(cfg.get("execution", {}).get("capture_limit_kb", 256)),
            env=effective_env(cfg),
            redact_output=cfg.get("redaction", {}).get("enabled", True),
        )
    except (OSError, PermissionError, FileNotFoundError) as exc:
        report.add(
            f"{report.level_id.lower()}.{command_key or 'command'}.launch",
            "INFRA_ERROR",
            "execution",
            "kOA-Linux validation command could not be launched.",
            evidence=f"{type(exc).__name__}: {exc}",
            recommendation=recommendation,
        )
        return

    combined = "\n".join(x for x in (result.get("stdout_tail", ""), result.get("stderr_tail", "")) if x)
    reports = referenced_gate_reports(cfg, combined) if include_gate_reports else []
    evidence = dict(result)
    if reports:
        evidence["referenced_gate_reports"] = reports
        for item in reports:
            path = item.get("path")
            if path:
                report.artifact(
                    "koa_gate_report",
                    path,
                    "Referenced kOA-Linux CI gate report captured from the target repository.",
                )
    missing = missing_python_modules(combined)
    if missing:
        evidence["missing_python_modules"] = missing

    if result.get("timed_out"):
        verdict = "INFRA_ERROR"
        message = "kOA-Linux validation timed out."
    elif result.get("exit_code") == 0:
        verdict = "PASS"
        message = "kOA-Linux validation passed."
    elif blocked_marker and blocked_marker.casefold() in combined.casefold():
        verdict = "BLOCKED"
        message = f"kOA-Linux validation reported BLOCKED ({blocked_marker})."
    else:
        verdict = "FAIL"
        message = "kOA-Linux validation failed."

    if missing and verdict != "PASS":
        message = "kOA-Linux validation could not import required Python module(s): " + ", ".join(missing) + "."
        recommendation = "Activate or install the kOA-Linux validation/test environment so the missing modules are importable."

    report.add(
        f"{report.level_id.lower()}.{command_key or 'command'}.result",
        verdict,
        "execution",
        message,
        evidence=evidence,
        recommendation=None if verdict == "PASS" else (recommendation or "Inspect the validator output and referenced kOA-Linux gate report."),
    )
    report.metrics["command"] = argv
    report.metrics["duration_seconds"] = result.get("duration_seconds")
