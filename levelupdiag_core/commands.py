"""Safe external command execution for LevelUpDiag-Koali.

This module owns subprocess creation only.  Commands are passed as argument
sequences and the normal execution path always uses ``shell=False``.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from .models import StepResult
from .verdicts import FAIL, INFRA_ERROR, PASS

_DEFAULT_TAIL_CHARS = 131072
_REPORT_DIRECTORY_NAME = "koa-ci-evidence"
_REPORT_NAME_SUFFIX = "-gate-report.json"
_REPORT_RE = re.compile(r"(?im)\breport=(?P<path>[^\r\n]+)")
_MODULE_NOT_FOUND_RE = re.compile(
    r"""ModuleNotFoundError:\s+No module named ['"](?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)['"]"""
)
_MAX_REFERENCED_REPORT_CHARS = 131072


def find_executable(name: str) -> str | None:
    """Return the resolved executable path available on ``PATH``.

    Empty names are rejected instead of being passed to platform lookup APIs.
    """

    candidate = str(name).strip()
    if not candidate:
        return None
    return shutil.which(candidate)


def _command_args(command: Sequence[str]) -> list[str]:
    if isinstance(command, (str, bytes)):
        raise TypeError("command must be a sequence of arguments, not a string")
    args = [os.fspath(item) if isinstance(item, os.PathLike) else item for item in command]
    if not args:
        raise ValueError("command must contain at least one argument")
    if not all(isinstance(item, str) for item in args):
        raise TypeError("every command argument must be a string or path-like value")
    if not args[0].strip():
        raise ValueError("command executable must not be empty")
    return args


def format_command(command: str | Sequence[str]) -> str:
    """Return a display-only representation of a command.

    This helper never executes the returned string.  String input is accepted
    only for display compatibility; :func:`run_cmd` itself requires a sequence.
    """

    if isinstance(command, str):
        return command
    args = _command_args(command)
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def _output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _tail(value: str, tail_chars: int) -> str:
    if tail_chars < 0:
        raise ValueError("tail_chars must be >= 0")
    if tail_chars == 0:
        return ""
    return value[-tail_chars:]


def missing_python_modules(output: str) -> list[str]:
    """Return unique Python module names reported as missing in command output."""

    return sorted({match.group("name") for match in _MODULE_NOT_FOUND_RE.finditer(output)})


def append_referenced_reports(
    output: str,
    *,
    cwd: str | Path | None = None,
    max_report_chars: int = _MAX_REFERENCED_REPORT_CHARS,
) -> str:
    """Append readable local report files explicitly referenced as ``report=...``.

    Public kOA-Linux gate scripts commonly emit a final ``report=<path>`` line
    when a gate fails or is blocked. LevelUpDiag records only JSON gate reports
    named ``*-gate-report.json`` below a ``koa-ci-evidence`` directory, keeping
    ``output.log`` self-contained without following arbitrary file references.

    The helper is opt-in: callers decide which trusted command outputs are
    eligible for local report expansion.
    """

    if max_report_chars < 0:
        raise ValueError("max_report_chars must be >= 0")
    base = Path(cwd).expanduser().resolve() if cwd is not None else Path.cwd().resolve()
    sections: list[str] = []
    seen: set[Path] = set()

    for match in _REPORT_RE.finditer(output):
        raw = match.group("path").strip().strip('"').strip("'")
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        try:
            path = candidate.resolve()
        except OSError:
            continue
        parts = {part.casefold() for part in path.parts}
        if (
            path in seen
            or _REPORT_DIRECTORY_NAME.casefold() not in parts
            or not path.name.casefold().endswith(_REPORT_NAME_SUFFIX)
            or not path.is_file()
        ):
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            sections.append(
                f"[LevelUpDiag] Referenced report could not be read: {path}\n"
                f"{type(exc).__name__}: {exc}"
            )
            continue

        if max_report_chars and len(text) > max_report_chars:
            half = max_report_chars // 2
            omitted = len(text) - (half * 2)
            text = (
                text[:half]
                + f"\n\n[LevelUpDiag] ... {omitted} report character(s) omitted ...\n\n"
                + text[-half:]
            )
        elif max_report_chars == 0:
            text = ""

        sections.append(
            f"[LevelUpDiag] Referenced report: {path}\n"
            + (text.rstrip() or "[empty report]")
        )

    if not sections:
        return output
    return output.rstrip() + "\n\n" + "\n\n".join(sections) + "\n"


def run_cmd(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: int | float = 120,
    name: str | None = None,
    env: Mapping[str, str] | None = None,
    tail_chars: int = _DEFAULT_TAIL_CHARS,
) -> StepResult:
    """Execute one external command and normalize its result.

    ``stdout`` and ``stderr`` are captured into one ordered text stream.  A
    non-zero process exit is a target/check ``FAIL``.  Launch failures and
    timeouts are infrastructure failures and therefore return ``INFRA_ERROR``.
    Environment values are passed to the child process but never included in
    the returned result or formatted output.
    """

    args = _command_args(command)
    if timeout <= 0:
        raise ValueError("timeout must be > 0")
    if tail_chars < 0:
        raise ValueError("tail_chars must be >= 0")

    resolved_cwd = Path(cwd).expanduser().resolve() if cwd is not None else Path.cwd().resolve()
    started = datetime.now().astimezone()
    started_at = started.isoformat(timespec="seconds")
    display = format_command(args)
    label = str(name).strip() if name is not None else ""

    verdict = INFRA_ERROR
    exit_code: int | None = None
    output = ""
    error: str | None = None

    try:
        completed = subprocess.run(
            args,
            cwd=str(resolved_cwd),
            env=dict(env) if env is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
        exit_code = int(completed.returncode)
        output = completed.stdout or ""
        verdict = PASS if exit_code == 0 else FAIL
    except subprocess.TimeoutExpired as exc:
        output = _output_text(exc.output)
        error = f"Command timed out after {timeout} seconds"
        verdict = INFRA_ERROR
    except OSError as exc:
        error = f"{type(exc).__name__}: {exc}"
        verdict = INFRA_ERROR

    ended = datetime.now().astimezone()
    if error:
        diagnostic = f"[{label}] {error}" if label else error
        output = f"{output.rstrip()}\n{diagnostic}".lstrip("\n")

    return StepResult(
        verdict=verdict,
        command=list(args),
        cwd=str(resolved_cwd),
        exit_code=exit_code,
        started_at=started_at,
        ended_at=ended.isoformat(timespec="seconds"),
        duration_seconds=round((ended - started).total_seconds(), 6),
        output_tail=_tail(output, tail_chars),
        error=error,
    )


def launch_console(
    command: Sequence[str],
    cwd: str | Path,
    title: str = "LevelUpDiag-Koali",
) -> subprocess.Popen[str]:
    """Launch a command in a console-capable child process using ``shell=False``.

    On Windows a new console is requested.  ``title`` is retained as part of
    the stable API but is deliberately not interpolated into a shell command.
    On other platforms the command is launched directly in the current
    terminal/session.
    """

    del title  # Never interpolate user-controlled title text into a shell.
    args = _command_args(command)
    resolved_cwd = Path(cwd).expanduser().resolve()
    kwargs: dict[str, object] = {
        "cwd": str(resolved_cwd),
        "shell": False,
        "text": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
    return subprocess.Popen(args, **kwargs)  # type: ignore[arg-type, return-value]
