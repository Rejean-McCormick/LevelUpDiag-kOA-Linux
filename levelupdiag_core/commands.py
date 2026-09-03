from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from .util import redact, tail_text

class CommandBlocked(RuntimeError):
    pass


def normalize_command(command):
    if isinstance(command, str):
        return shlex.split(command, posix=(os.name != "nt"))
    if isinstance(command, list) and all(isinstance(x, str) for x in command):
        return command
    raise ValueError("command must be a string or list of strings")


def which(name):
    return shutil.which(name)


def run_command(command, *, cwd: Path, timeout_seconds: int, capture_limit_kb=256,
                env=None, redact_output=True):
    argv = normalize_command(command)
    if not argv:
        raise ValueError("empty command")
    started = time.monotonic()
    try:
        cp = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
        timed_out = False
        code = cp.returncode
        out, err = cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired as e:
        timed_out = True
        code = None
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    duration = round(time.monotonic() - started, 3)
    if redact_output:
        out, err = redact(out), redact(err)
    limit = int(capture_limit_kb) * 1024
    return {
        "argv": argv,
        "cwd": str(cwd),
        "exit_code": code,
        "timed_out": timed_out,
        "duration_seconds": duration,
        "stdout_tail": tail_text(out, limit),
        "stderr_tail": tail_text(err, limit),
    }
