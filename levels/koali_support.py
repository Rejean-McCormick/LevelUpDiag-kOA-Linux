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



def _ui_modularity_base_root(cfg, section) -> Path:
    """Resolve the explicitly configured product-repository base directory."""
    tool_root = Path(cfg["_tool_root"]).resolve(strict=False)
    raw = section.get("base_root", "..")
    candidate = Path(str(raw)).expanduser()
    if not candidate.is_absolute():
        candidate = tool_root / candidate
    return candidate.resolve(strict=False)


def _configured_product_path(product_root: Path, raw: str) -> Path | None:
    """Resolve one product-relative marker without allowing it to escape the product root."""
    candidate = Path(raw)
    if candidate.is_absolute():
        return None
    resolved = (product_root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(product_root)
    except ValueError:
        return None
    return resolved


def collect_ui_modularity_findings(cfg) -> tuple[list[dict], dict]:
    """Evaluate configured standalone/integrated product UI boundaries read-only.

    LevelUpDiag deliberately does not define Koali's UI manifest filenames or product
    framework. The caller supplies marker paths and optional private-import tokens in
    configuration. Missing optional products are accepted as a valid removal state.
    """
    section = cfg.get("ui_modularity", {})
    if not isinstance(section, dict) or not section.get("enabled", False):
        return [], {"enabled": False, "configured_products": 0, "checked_products": 0}

    products = section.get("products", [])
    if not isinstance(products, list):
        return ([{
            "id": "n06.ui_modularity.config",
            "verdict": "CONFIG_ERROR",
            "category": "configuration",
            "message": "ui_modularity.products must be a list.",
        }], {"enabled": True, "configured_products": 0, "checked_products": 0})

    base_root = _ui_modularity_base_root(cfg, section)
    findings: list[dict] = []
    checked = 0
    optional_absent = 0

    for index, item in enumerate(products):
        if not isinstance(item, dict):
            findings.append({
                "id": f"n06.ui_modularity.product.{index}",
                "verdict": "CONFIG_ERROR",
                "category": "configuration",
                "message": "UI modularity product entry must be an object.",
            })
            continue

        product_id = str(item.get("id") or f"product-{index}").strip()
        raw_root = item.get("root")
        if not product_id or not isinstance(raw_root, str) or not raw_root.strip():
            findings.append({
                "id": f"n06.ui_modularity.product.{index}",
                "verdict": "CONFIG_ERROR",
                "category": "configuration",
                "message": "UI modularity product entry requires non-empty id and root values.",
            })
            continue

        candidate = Path(raw_root).expanduser()
        product_root = candidate if candidate.is_absolute() else base_root / candidate
        product_root = product_root.resolve(strict=False)
        required = bool(item.get("required", False))

        if not product_root.is_dir():
            if required:
                findings.append({
                    "id": f"n06.ui_modularity.{product_id}.root",
                    "verdict": "BLOCKED",
                    "category": "integration",
                    "message": f"Required product UI repository '{product_id}' is unavailable.",
                    "evidence": {"root": str(product_root), "required": True},
                    "recommendation": "Provide the configured product repository before qualifying its UI integration.",
                })
            else:
                optional_absent += 1
                findings.append({
                    "id": f"n06.ui_modularity.{product_id}.removed",
                    "verdict": "PASS",
                    "category": "integration",
                    "message": f"Optional product UI '{product_id}' is absent; independent removal is accepted.",
                    "evidence": {"root": str(product_root), "required": False, "state": "absent_optional"},
                })
            continue

        checked += 1
        marker_groups = (
            ("standalone_markers", "standalone"),
            ("integration_markers", "integrated contribution"),
        )
        for field, label in marker_groups:
            raw_markers = item.get(field, [])
            if raw_markers in (None, ""):
                raw_markers = []
            if not isinstance(raw_markers, list) or not all(isinstance(value, str) and value for value in raw_markers):
                findings.append({
                    "id": f"n06.ui_modularity.{product_id}.{field}",
                    "verdict": "CONFIG_ERROR",
                    "category": "configuration",
                    "message": f"{field} for '{product_id}' must be a list of relative paths.",
                })
                continue

            missing: list[str] = []
            invalid: list[str] = []
            for raw_marker in raw_markers:
                marker = _configured_product_path(product_root, raw_marker)
                if marker is None:
                    invalid.append(raw_marker)
                elif not marker.exists():
                    missing.append(raw_marker)

            if invalid:
                findings.append({
                    "id": f"n06.ui_modularity.{product_id}.{field}.path",
                    "verdict": "CONFIG_ERROR",
                    "category": "configuration",
                    "message": f"Configured {label} marker escapes the product repository.",
                    "evidence": {"invalid_paths": invalid},
                })
            elif missing:
                findings.append({
                    "id": f"n06.ui_modularity.{product_id}.{field}.missing",
                    "verdict": "FAIL",
                    "category": "integration",
                    "message": f"Product UI '{product_id}' is missing configured {label} marker(s).",
                    "evidence": {"missing_paths": missing, "root": str(product_root)},
                    "recommendation": "Restore the product-owned standalone/integrated UI contract or update the explicit diagnostic configuration.",
                })
            elif raw_markers:
                findings.append({
                    "id": f"n06.ui_modularity.{product_id}.{field}",
                    "verdict": "PASS",
                    "category": "integration",
                    "message": f"Product UI '{product_id}' exposes the configured {label} marker(s).",
                    "evidence": {"paths": raw_markers},
                })

        scan_files = item.get("scan_files", [])
        forbidden = item.get("forbidden_private_ui_tokens", [])
        if scan_files in (None, ""):
            scan_files = []
        if forbidden in (None, ""):
            forbidden = []
        if not isinstance(scan_files, list) or not all(isinstance(value, str) and value for value in scan_files):
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.scan_files",
                "verdict": "CONFIG_ERROR",
                "category": "configuration",
                "message": f"scan_files for '{product_id}' must be a list of relative file paths.",
            })
            continue
        if not isinstance(forbidden, list) or not all(isinstance(value, str) and value for value in forbidden):
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.forbidden_tokens",
                "verdict": "CONFIG_ERROR",
                "category": "configuration",
                "message": f"forbidden_private_ui_tokens for '{product_id}' must be a list of strings.",
            })
            continue
        if forbidden and not scan_files:
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.scan",
                "verdict": "CONFIG_ERROR",
                "category": "configuration",
                "message": f"Product UI '{product_id}' configures forbidden private UI tokens but no scan_files.",
            })
            continue

        violations: list[dict] = []
        invalid_scan_paths: list[str] = []
        missing_scan_paths: list[str] = []
        for raw_file in scan_files:
            scan_path = _configured_product_path(product_root, raw_file)
            if scan_path is None:
                invalid_scan_paths.append(raw_file)
                continue
            if not scan_path.is_file():
                missing_scan_paths.append(raw_file)
                continue
            try:
                text = scan_path.read_text(encoding="utf-8", errors="replace")[:524288]
            except OSError as exc:
                findings.append({
                    "id": f"n06.ui_modularity.{product_id}.scan.read",
                    "verdict": "INFRA_ERROR",
                    "category": "execution",
                    "message": f"Could not read configured UI dependency scan file for '{product_id}'.",
                    "evidence": {"path": raw_file, "error": f"{type(exc).__name__}: {exc}"},
                })
                continue
            for token in forbidden:
                if token in text:
                    violations.append({"path": raw_file, "token": token})

        if invalid_scan_paths:
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.scan.path",
                "verdict": "CONFIG_ERROR",
                "category": "configuration",
                "message": f"Configured UI dependency scan path escapes product repository '{product_id}'.",
                "evidence": {"invalid_paths": invalid_scan_paths},
            })
        if missing_scan_paths:
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.scan.missing",
                "verdict": "CONFIG_ERROR",
                "category": "configuration",
                "message": f"Configured UI dependency scan file is missing for '{product_id}'.",
                "evidence": {"missing_paths": missing_scan_paths},
            })
        if violations:
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.private_ui_dependency",
                "verdict": "FAIL",
                "category": "integration",
                "message": f"Product UI '{product_id}' references configured private UI dependency token(s).",
                "evidence": {"violations": violations},
                "recommendation": "Replace private cross-product UI imports with the shared Koali UI contract or an explicit public integration contract.",
            })
        elif forbidden and scan_files and not invalid_scan_paths and not missing_scan_paths:
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.private_ui_dependency",
                "verdict": "PASS",
                "category": "integration",
                "message": f"Product UI '{product_id}' has no configured private cross-product UI dependency token in the inspected files.",
                "evidence": {"scan_files": scan_files, "checked_tokens": len(forbidden)},
            })

        if not any(f["id"].startswith(f"n06.ui_modularity.{product_id}.") for f in findings):
            findings.append({
                "id": f"n06.ui_modularity.{product_id}.root",
                "verdict": "PASS",
                "category": "integration",
                "message": f"Product UI repository '{product_id}' is available; no deeper UI markers were configured.",
                "evidence": {"root": str(product_root)},
            })

    return findings, {
        "enabled": True,
        "base_root": str(base_root),
        "configured_products": len(products),
        "checked_products": checked,
        "optional_absent_products": optional_absent,
    }


def run_ui_modularity_diagnostics(cfg, report) -> None:
    findings, metrics = collect_ui_modularity_findings(cfg)
    report.metrics["ui_modularity"] = metrics
    for item in findings:
        report.add(
            item["id"],
            item["verdict"],
            item["category"],
            item["message"],
            evidence=item.get("evidence"),
            recommendation=item.get("recommendation"),
            path=item.get("path"),
            data=item.get("data"),
        )

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
