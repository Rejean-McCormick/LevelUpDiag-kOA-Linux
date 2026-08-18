"""Contracts validation level for LevelUpDiag-Koali."""

from __future__ import annotations

from datetime import datetime
import os
import shlex
from pathlib import Path

from levelupdiag_core.commands import append_referenced_reports, missing_python_modules, run_cmd
from levelupdiag_core.config import AppConfig, load_config
from levelupdiag_core.logs import run_directory, update_latest, write_output_log
from levelupdiag_core.manifest import get_level
from levelupdiag_core.models import Finding, LevelResult, StepResult
from levelupdiag_core.reports import write_level_result
from levelupdiag_core.verdicts import CONFIG_ERROR, INFRA_ERROR, SKIP, exit_code

LEVEL_ID = "N04"
LEVEL_NAME = "Contracts"
_COMMAND_KEY = "contracts"
_REQUIRED_COMMAND = True


def _parse_command(command: str) -> list[str]:
    """Split one configured command without invoking a shell."""

    text = command.strip()
    if not text:
        return []
    if os.name != "nt":
        return shlex.split(text, posix=True)

    # Use the Windows command-line parser without ever invoking a shell.
    # This preserves quoted paths and Windows backslashes correctly.
    import ctypes

    argc = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = parse(text, ctypes.byref(argc))
    if not argv:
        raise ValueError("Windows command line could not be parsed")
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        local_free = ctypes.windll.kernel32.LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p
        local_free(ctypes.cast(argv, ctypes.c_void_p))


def _local_result(verdict: str, finding: Finding, started: datetime) -> LevelResult:
    ended = datetime.now().astimezone()
    return LevelResult(
        level=LEVEL_ID,
        name=LEVEL_NAME,
        verdict=verdict,
        findings=[finding],
        started_at=started.isoformat(timespec="seconds"),
        ended_at=ended.isoformat(timespec="seconds"),
        duration_seconds=round((ended - started).total_seconds(), 6),
    )


def _from_step(step: StepResult) -> LevelResult:
    findings: list[Finding] = []
    if step.verdict != "PASS":
        missing_modules = missing_python_modules(step.output_tail)
        if missing_modules:
            joined = ", ".join(missing_modules)
            message = (
                f"Configured {_COMMAND_KEY} validation could not import required Python "
                f"module(s): {joined}."
            )
            recommendation = (
                "Activate or install the kOA-Linux validation/test environment so these "
                f"modules are importable: {joined}."
            )
        else:
            message = (
                f"Configured {_COMMAND_KEY} validation command failed."
                if step.verdict == "FAIL"
                else f"Configured {_COMMAND_KEY} validation command could not complete."
            )
            recommendation = "Inspect the configured public kOA-Linux command and its output."
        findings.append(
            Finding(
                id=f"{LEVEL_ID.lower()}.{_COMMAND_KEY}.command",
                severity=step.verdict,
                message=message,
                category="execution",
                evidence=step.error or step.output_tail or None,
                recommendation=recommendation,
                data={"missing_python_modules": missing_modules} if missing_modules else {},
            )
        )
    return LevelResult(
        level=LEVEL_ID,
        name=LEVEL_NAME,
        verdict=step.verdict,
        findings=findings,
        started_at=step.started_at,
        ended_at=step.ended_at,
        duration_seconds=step.duration_seconds,
        exit_code=step.exit_code,
        command=list(step.command),
        cwd=step.cwd,
        output_tail=step.output_tail,
    )


def run(config: AppConfig | None = None) -> LevelResult:
    """Run the configured public kOA-Linux validation command."""

    cfg = load_config() if config is None else config
    started = datetime.now().astimezone()
    command_text = cfg.command(_COMMAND_KEY).strip()
    if not command_text:
        verdict = CONFIG_ERROR if _REQUIRED_COMMAND else SKIP
        return _local_result(
            verdict,
            Finding(
                id=f"{LEVEL_ID.lower()}.{_COMMAND_KEY}.command.missing",
                severity=verdict,
                message=f"Configured command '{_COMMAND_KEY}' is empty.",
                category="configuration",
                recommendation=(
                    f"Set commands.{_COMMAND_KEY} to a documented public kOA-Linux command."
                    if _REQUIRED_COMMAND
                    else f"Configure commands.{_COMMAND_KEY} when this optional validation is available."
                ),
            ),
            started,
        )

    try:
        args = _parse_command(command_text)
    except ValueError as exc:
        return _local_result(
            CONFIG_ERROR,
            Finding(
                id=f"{LEVEL_ID.lower()}.{_COMMAND_KEY}.command.invalid",
                severity=CONFIG_ERROR,
                message=f"Configured command '{_COMMAND_KEY}' cannot be parsed safely.",
                category="configuration",
                evidence=str(exc),
                recommendation=f"Correct commands.{_COMMAND_KEY} in the local configuration.",
            ),
            started,
        )

    if not args:
        return _local_result(
            CONFIG_ERROR if _REQUIRED_COMMAND else SKIP,
            Finding(
                id=f"{LEVEL_ID.lower()}.{_COMMAND_KEY}.command.empty",
                severity=CONFIG_ERROR if _REQUIRED_COMMAND else SKIP,
                message=f"Configured command '{_COMMAND_KEY}' has no executable arguments.",
                category="configuration",
            ),
            started,
        )

    level_info = get_level(LEVEL_ID, root=cfg.diagnostics_root_path)
    step = run_cmd(
        args,
        cwd=cfg.target_root_path,
        timeout=level_info.timeout_seconds,
        name=f"{LEVEL_ID} {LEVEL_NAME}",
        env=cfg.env(),
    )
    step.output_tail = append_referenced_reports(
        step.output_tail,
        cwd=cfg.target_root_path,
    )
    if step.verdict not in {"PASS", "FAIL", INFRA_ERROR}:
        # This protects the frozen Level protocol if run_cmd evolves later.
        return _local_result(
            CONFIG_ERROR,
            Finding(
                id=f"{LEVEL_ID.lower()}.{_COMMAND_KEY}.unexpected-step-verdict",
                severity=CONFIG_ERROR,
                message=f"Unexpected StepResult verdict: {step.verdict}.",
                category="internal-contract",
            ),
            started,
        )
    return _from_step(step)


def main() -> int:
    """Standalone entry point that persists this level's result and log."""

    config = load_config()
    result = run(config)
    level_info = get_level(LEVEL_ID, root=config.diagnostics_root_path)
    try:
        started = datetime.fromisoformat(result.started_at) if result.started_at else datetime.now().astimezone()
    except ValueError:
        started = datetime.now().astimezone()
    directory = run_directory(config, level_info, started)
    result_path = write_level_result(result, directory / "result.json")
    write_output_log(directory, result.output_tail)
    update_latest(config, level_info, result_path)
    return exit_code(result.verdict)


if __name__ == "__main__":
    raise SystemExit(main())
