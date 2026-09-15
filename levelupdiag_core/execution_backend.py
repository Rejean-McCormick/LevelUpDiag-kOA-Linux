from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable, Iterable


class ExecutionBackendError(RuntimeError):
    """Raised when the desktop console cannot establish its execution backend."""


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    backend: str
    runtime: str
    command: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.backend.upper()} / {self.runtime}"


def _backend_name(cfg: dict, platform_name: str) -> str:
    section = cfg.get("desktop_console", {})
    requested = str(section.get("execution_backend", "auto")).strip().casefold()
    if requested not in {"auto", "native", "wsl"}:
        raise ExecutionBackendError(
            "desktop_console.execution_backend must be one of: auto, native, wsl"
        )
    if requested == "auto":
        return "wsl" if platform_name == "nt" else "native"
    return requested


def _wsl_path(
    path: Path,
    *,
    wsl_executable: str,
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    result = run(
        [wsl_executable, "--exec", "wslpath", "-a", "-u", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    converted = (result.stdout or "").strip()
    if result.returncode != 0 or not converted.startswith("/"):
        detail = (result.stderr or result.stdout or "wslpath failed").strip()
        raise ExecutionBackendError(f"Unable to translate Windows path for WSL: {detail}")
    return converted


def _wsl_python(
    *,
    wsl_executable: str,
    candidates: Iterable[str],
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    checked: list[str] = []
    for raw in candidates:
        candidate = str(raw).strip()
        if not candidate:
            continue
        checked.append(candidate)
        result = run(
            [wsl_executable, "--exec", candidate, "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    raise ExecutionBackendError(
        "No usable Python interpreter was found in WSL "
        f"(checked: {', '.join(checked) or 'none'})."
    )


def _wsl_environment(
    *,
    wsl_executable: str,
    python: str,
    path_prepend: Iterable[str],
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[str, str]:
    """Return HOME and an augmented PATH from the selected WSL runtime.

    Windows-launched ``wsl.exe --exec`` sessions can expose a smaller PATH than an
    interactive WSL session. Query the WSL process environment directly, then prepend
    configured user tool locations without invoking a shell.
    """

    probe = (
        "import json, os; "
        "print(json.dumps({'home': os.environ.get('HOME', ''), "
        "'path': os.environ.get('PATH', '')}))"
    )
    result = run(
        [wsl_executable, "--exec", python, "-c", probe],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "WSL environment probe failed").strip()
        raise ExecutionBackendError(f"Unable to inspect the WSL runtime environment: {detail}")
    try:
        data = json.loads((result.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise ExecutionBackendError("WSL environment probe returned invalid JSON") from exc

    home = str(data.get("home", "")).strip()
    current_path = str(data.get("path", "")).strip()
    if not home.startswith("/"):
        raise ExecutionBackendError("WSL HOME is unavailable or invalid")

    entries: list[str] = []
    for raw in path_prepend:
        item = str(raw).strip()
        if not item:
            continue
        if item == "~":
            item = home
        elif item.startswith("~/"):
            item = f"{home}/{item[2:]}"
        if item not in entries:
            entries.append(item)
    for item in current_path.split(":"):
        if item and item not in entries:
            entries.append(item)
    return home, ":".join(entries)


def build_launch_plan(
    tool_root: Path,
    selection: str,
    mode: str,
    cfg: dict,
    *,
    platform_name: str | None = None,
    native_python: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> LaunchPlan:
    """Build a shell-free LevelUpDiag launch command for the desktop console.

    AUTO intentionally means WSL on Windows and native execution elsewhere. kOA-Linux
    qualification depends on a Linux/Rust/native toolchain; silently falling back to
    Windows Python would turn environment failures into misleading target evidence.
    """

    host = os.name if platform_name is None else platform_name
    backend = _backend_name(cfg, host)
    script = tool_root / "levelupdiag.py"

    if backend == "native":
        python = native_python or sys.executable
        return LaunchPlan(
            backend="native",
            runtime=Path(python).name or python,
            command=(python, str(script), "run", selection, "--mode", mode),
        )

    if host != "nt":
        raise ExecutionBackendError("WSL execution backend is only available from Windows.")

    wsl = which("wsl.exe") or which("wsl")
    if not wsl:
        raise ExecutionBackendError(
            "WSL is required by desktop_console.execution_backend=auto/wsl on Windows, "
            "but wsl.exe was not found. Set the backend explicitly to 'native' only if "
            "the complete kOA-Linux toolchain is intentionally installed on Windows."
        )

    section = cfg.get("desktop_console", {})
    candidates = section.get("wsl_python_candidates", ["python3", "python"])
    if not isinstance(candidates, list):
        raise ExecutionBackendError("desktop_console.wsl_python_candidates must be a list")

    wsl_script = _wsl_path(script, wsl_executable=wsl, run=run)
    python = _wsl_python(wsl_executable=wsl, candidates=candidates, run=run)
    path_prepend = section.get("wsl_path_prepend", ["~/.local/bin", "~/.cargo/bin"])
    if not isinstance(path_prepend, list):
        raise ExecutionBackendError("desktop_console.wsl_path_prepend must be a list")
    _home, runtime_path = _wsl_environment(
        wsl_executable=wsl, python=python, path_prepend=path_prepend, run=run
    )
    return LaunchPlan(
        backend="wsl",
        runtime=f"{python} + user PATH",
        command=(
            wsl, "--exec", "/usr/bin/env", f"PATH={runtime_path}",
            python, wsl_script, "run", selection, "--mode", mode,
        ),
    )
