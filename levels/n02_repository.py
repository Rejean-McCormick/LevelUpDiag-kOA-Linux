from __future__ import annotations
from pathlib import Path
from levelupdiag_core.commands import run_command, which
from levelupdiag_core.vcs import git_info


def run(cfg, report):
    target = Path(cfg["_target_root"])
    gi = git_info(target)
    if not gi.get("available"):
        report.add("koali.git.available", "WARN", "repository", "Git is not available; repository observations are limited.")
        return
    if not gi.get("repository"):
        report.add("koali.git.repository", "WARN", "repository", "Target directory is not an observable Git worktree.", path=str(target))
        return
    report.add("koali.git.repository", "PASS", "repository", "kOA-Linux Git worktree detected.", evidence={"branch":gi.get("branch") or "(detached)","head":gi.get("head")})
    ignored = run_command(["git","check-ignore","-q","--",".levelupdiag"], cwd=target, timeout_seconds=10, capture_limit_kb=16)
    report.add("koali.control_dir.ignored", "PASS" if ignored.get("exit_code") == 0 else "WARN", "repository",
               "Generated .levelupdiag evidence is ignored by Git." if ignored.get("exit_code") == 0 else "Generated .levelupdiag evidence is not ignored by Git.",
               evidence={"path":".levelupdiag/"},
               recommendation=None if ignored.get("exit_code") == 0 else "Add .levelupdiag/ to the kOA-Linux root .gitignore.")
    status = run_command(["git","status","--porcelain=v1","--untracked-files=normal"], cwd=target, timeout_seconds=30, capture_limit_kb=128)
    if status.get("timed_out"):
        report.add("koali.git.status", "INFRA_ERROR", "repository", "Git status timed out.")
    elif status.get("exit_code") != 0:
        report.add("koali.git.status", "WARN", "repository", "Git worktree status could not be determined.", evidence=status)
    else:
        dirty = bool(status.get("stdout_tail", "").strip())
        report.add("koali.git.worktree", "WARN" if dirty else "PASS", "repository",
                   "Git worktree contains tracked or untracked changes." if dirty else "Git worktree is clean.",
                   evidence=status.get("stdout_tail", "")[-4000:] if dirty else {"dirty":False},
                   recommendation="Review the working tree state before interpreting validation evidence." if dirty else None)
    report.metrics["git"] = gi
