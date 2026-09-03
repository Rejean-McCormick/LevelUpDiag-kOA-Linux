from __future__ import annotations

from pathlib import Path
from .commands import run_command, which


def git_info(target: Path):
    if not which("git") or not (target / ".git").exists():
        return {"available": bool(which("git")), "repository": False}
    def g(args, timeout=15):
        return run_command(["git", *args], cwd=target, timeout_seconds=timeout, capture_limit_kb=64)
    head = g(["rev-parse", "--verify", "HEAD"])
    branch = g(["branch", "--show-current"])
    status = g(["status", "--porcelain=v1", "--untracked-files=no"])
    return {
        "available": True,
        "repository": True,
        "head": head["stdout_tail"].strip() if head["exit_code"] == 0 else None,
        "branch": branch["stdout_tail"].strip() if branch["exit_code"] == 0 else None,
        "tracked_status": status["stdout_tail"],
    }
