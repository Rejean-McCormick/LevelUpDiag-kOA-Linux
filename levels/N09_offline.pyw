"""N09 — run the configured public offline validation for kOA-Linux."""

from __future__ import annotations

import os
import shlex
from datetime import datetime

from levelupdiag_core.commands import append_referenced_reports, missing_python_modules, run_cmd
from levelupdiag_core.config import AppConfig, load_config
from levelupdiag_core.logs import run_directory, update_latest, write_output_log
from levelupdiag_core.manifest import get_level
from levelupdiag_core.models import Finding, LevelResult
from levelupdiag_core.reports import write_level_result
from levelupdiag_core.verdicts import BLOCKED, SKIP, exit_code

LEVEL_ID = "N09"
LEVEL_NAME = "Offline"
_COMMAND_KEY = "offline"


def _command_args(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def run(config: AppConfig | None = None) -> LevelResult:
    cfg = config if config is not None else load_config()
    configured = cfg.command(_COMMAND_KEY).strip()
    if not configured:
        return LevelResult(
            level=LEVEL_ID,
            name=LEVEL_NAME,
            verdict=SKIP,
            findings=[
                Finding(
                    id="n09.offline.command-not-configured",
                    severity=SKIP,
                    message="No public offline validation command is configured.",
                    category="configuration",
                    recommendation="Configure commands.offline when this validation is available.",
                )
            ],
            cwd=str(cfg.target_root_path),
        )

    try:
        args = _command_args(configured)
    except ValueError as exc:
        from levelupdiag_core.verdicts import CONFIG_ERROR

        return LevelResult(
            level=LEVEL_ID,
            name=LEVEL_NAME,
            verdict=CONFIG_ERROR,
            findings=[
                Finding(
                    id="n09.offline.command-parse-error",
                    severity=CONFIG_ERROR,
                    message=f"Configured offline command cannot be parsed: {exc}",
                    category="configuration",
                )
            ],
            cwd=str(cfg.target_root_path),
        )

    step = run_cmd(
        args,
        cwd=cfg.target_root_path,
        timeout=get_level(LEVEL_ID, cfg.diagnostics_root_path).timeout_seconds,
        name=LEVEL_NAME,
        env=cfg.env(),
    )
    step.output_tail = append_referenced_reports(
        step.output_tail,
        cwd=cfg.target_root_path,
    )
    normalized_verdict = step.verdict
    blocked_marker = "offline: blocked" in step.output_tail.lower()
    if step.verdict == "FAIL" and blocked_marker:
        normalized_verdict = BLOCKED

    findings: list[Finding] = []
    if normalized_verdict != "PASS":
        missing_modules = missing_python_modules(step.output_tail)
        if normalized_verdict == BLOCKED:
            message = "Offline validation reported BLOCKED."
            recommendation = "Inspect the captured gate report to identify the unmet prerequisite."
        elif missing_modules:
            joined = ", ".join(missing_modules)
            message = (
                f"Offline validation could not import required Python module(s): {joined}."
            )
            recommendation = (
                "Activate or install the kOA-Linux validation/test environment so these "
                f"modules are importable: {joined}."
            )
        else:
            message = step.error or f"Offline validation exited with code {step.exit_code}."
            recommendation = "Inspect the captured command output and referenced gate report."
        findings.append(
            Finding(
                id="n09.offline.command-result",
                severity=normalized_verdict,
                message=message,
                category="execution",
                evidence=step.output_tail or None,
                recommendation=recommendation,
                data={"missing_python_modules": missing_modules} if missing_modules else {},
            )
        )
    return LevelResult(
        level=LEVEL_ID,
        name=LEVEL_NAME,
        verdict=normalized_verdict,
        findings=findings,
        started_at=step.started_at,
        ended_at=step.ended_at,
        duration_seconds=step.duration_seconds,
        exit_code=step.exit_code,
        command=step.command,
        cwd=step.cwd,
        output_tail=step.output_tail,
    )


def main() -> int:
    cfg = load_config()
    started = datetime.now().astimezone()
    result = run(cfg)
    level = get_level(LEVEL_ID, cfg.diagnostics_root_path)
    directory = run_directory(cfg, level, started)
    result_path = write_level_result(result, directory / "result.json")
    write_output_log(directory, result.output_tail)
    update_latest(cfg, level, result_path)
    return exit_code(result.verdict)


if __name__ == "__main__":
    raise SystemExit(main())
