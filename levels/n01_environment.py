from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from levelupdiag_core.commands import normalize_command, run_command, which


def _available(name: str):
    if name.casefold() in {"python", "python3", "py"}:
        return True, sys.executable
    path = which(name)
    return bool(path), path


def _effective_env(cfg) -> dict[str, str]:
    env = dict(os.environ)
    configured = cfg.get("env", {})
    if isinstance(configured, dict):
        env.update({str(k): str(v) for k, v in configured.items()})
    return env


def run(cfg, report):
    target = Path(cfg["_target_root"])
    target_ok = target.is_dir()
    report.add(
        "koali.target.root",
        "PASS" if target_ok else "CONFIG_ERROR",
        "environment",
        "kOA-Linux target repository root is available." if target_ok else "kOA-Linux target repository root is unavailable.",
        path=str(target),
        recommendation=None if target_ok else "Set target_repo_root to the actual kOA-Linux repository root.",
    )
    if not target_ok:
        return

    report.add(
        "koali.runtime",
        "PASS",
        "environment",
        "Runtime context detected.",
        evidence={"platform": platform.platform(), "python": sys.version.split()[0], "executable": sys.executable},
    )

    toolchain = cfg.get("toolchain", {})
    missing_required: list[str] = []
    for required, bucket in ((True, "required"), (False, "optional")):
        for name in toolchain.get(bucket, []):
            name = str(name)
            ok, path = _available(name)
            if required and not ok:
                missing_required.append(name)
            verdict = "PASS" if ok else ("BLOCKED" if required else "WARN")
            report.add(
                f"koali.tool.{name}",
                verdict,
                "environment",
                f"Tool '{name}' is available." if ok else f"Tool '{name}' is not available on PATH.",
                evidence=path,
                recommendation=None if ok else (
                    f"Install or expose '{name}' before running kOA-Linux validation."
                    if required
                    else f"Install '{name}' if optional Koali validations need it."
                ),
            )

    if missing_required:
        return

    sync_command = cfg.get("environment_sync_command")
    if sync_command in (None, "", []):
        report.add(
            "koali.environment.sync",
            "CONFIG_ERROR",
            "environment",
            "The documented kOA-Linux dependency synchronization command is not configured.",
            recommendation="Configure environment_sync_command as: uv sync --frozen --all-groups.",
        )
        return

    try:
        argv = normalize_command(sync_command)
        result = run_command(
            argv,
            cwd=target,
            timeout_seconds=max(int(cfg.get("execution", {}).get("default_timeout_seconds", 120)), 300),
            capture_limit_kb=int(cfg.get("execution", {}).get("capture_limit_kb", 256)),
            env=_effective_env(cfg),
            redact_output=cfg.get("redaction", {}).get("enabled", True),
        )
    except (OSError, PermissionError, FileNotFoundError, ValueError) as exc:
        report.add(
            "koali.environment.sync",
            "INFRA_ERROR",
            "environment",
            "The kOA-Linux dependency synchronization command could not be launched.",
            evidence=f"{type(exc).__name__}: {exc}",
            recommendation="Verify uv and the kOA-Linux repository environment.",
        )
        return

    if result.get("timed_out"):
        verdict = "INFRA_ERROR"
        message = "kOA-Linux dependency synchronization timed out."
    elif result.get("exit_code") == 0:
        verdict = "PASS"
        message = "kOA-Linux dependency environment is synchronized from the frozen lock state."
    else:
        verdict = "BLOCKED"
        message = "kOA-Linux dependency synchronization failed; downstream validation cannot be trusted."

    report.add(
        "koali.environment.sync",
        verdict,
        "environment",
        message,
        evidence=result,
        recommendation=None if verdict == "PASS" else "Run 'uv sync --frozen --all-groups' from the kOA-Linux repository root and resolve the reported dependency issue.",
    )
    report.metrics["environment_sync_command"] = argv
    report.metrics["environment_sync_duration_seconds"] = result.get("duration_seconds")
