from __future__ import annotations

from pathlib import Path

from levelupdiag_core.commands import run_command
from levelupdiag_core.vcs import git_info


def _formal_verdict(cfg, strict="CONFIG_ERROR"):
    return "WARN" if cfg.get("_mode") == "debug" else strict


def run(cfg, report):
    target = Path(cfg["_target_root"]).resolve(strict=False)
    mode = cfg.get("_mode", "debug")
    gi = git_info(target)
    if not gi.get("available"):
        report.add(
            "koali.git.available", "WARN", "repository",
            "Git is not available; repository observations are limited. This does not block DEBUG.",
        )
        return
    if not gi.get("repository"):
        report.add(
            "koali.git.repository",
            _formal_verdict(cfg),
            "repository",
            "Configured target directory is not an observable Git worktree.",
            path=str(target),
            recommendation="Use VALIDATION/RELEASE only when repository provenance is required.",
        )
        return

    top = run_command(["git", "rev-parse", "--show-toplevel"], cwd=target, timeout_seconds=10, capture_limit_kb=16)
    top_text = (top.get("stdout_tail") or "").strip()
    try:
        git_root = Path(top_text).resolve(strict=False) if top_text else None
    except (OSError, ValueError):
        git_root = None

    if top.get("exit_code") != 0 or git_root is None:
        report.add("koali.git.root", "WARN", "repository", "Git repository root could not be resolved.", evidence=top)
    elif git_root != target:
        report.add(
            "koali.git.root",
            _formal_verdict(cfg),
            "repository",
            "target_repo_root does not point at the Git top-level directory.",
            evidence={"configured_target": str(target), "git_top_level": str(git_root), "diagnostic_mode": mode},
            recommendation="This is advisory in DEBUG; correct target/provenance before VALIDATION or RELEASE.",
        )
    else:
        report.add("koali.git.root", "PASS", "repository", "target_repo_root matches the Git top-level directory.", path=str(target))

    report.add(
        "koali.git.repository",
        "PASS",
        "repository",
        "Git worktree detected for repository observations.",
        evidence={"branch": gi.get("branch") or "(detached)", "head": gi.get("head")},
    )

    ignored = run_command(["git", "check-ignore", "-q", "--", ".levelupdiag"], cwd=target, timeout_seconds=10, capture_limit_kb=16)
    report.add(
        "koali.control_dir.ignored",
        "PASS" if ignored.get("exit_code") == 0 else "WARN",
        "repository",
        "Generated .levelupdiag evidence is ignored by Git." if ignored.get("exit_code") == 0 else "Generated .levelupdiag evidence is not ignored by Git.",
        evidence={"path": ".levelupdiag/"},
        recommendation=None if ignored.get("exit_code") == 0 else "Ignore .levelupdiag/ before strict validation/release workflows.",
    )

    status = run_command(["git", "status", "--porcelain=v1", "--untracked-files=normal"], cwd=target, timeout_seconds=30, capture_limit_kb=128)
    if status.get("timed_out"):
        verdict = "WARN" if mode == "debug" else "INFRA_ERROR"
        report.add("koali.git.status", verdict, "repository", "Git status timed out; DEBUG can continue.")
    elif status.get("exit_code") != 0:
        report.add("koali.git.status", "WARN", "repository", "Git worktree status could not be determined.", evidence=status)
    else:
        dirty = bool(status.get("stdout_tail", "").strip())
        report.add(
            "koali.git.worktree",
            "WARN" if dirty else "PASS",
            "repository",
            "Git worktree contains local changes; this is advisory and does not block DEBUG." if dirty else "Git worktree is clean.",
            evidence=status.get("stdout_tail", "")[-4000:] if dirty else {"dirty": False},
            recommendation="Review local changes before VALIDATION/RELEASE if provenance matters." if dirty else None,
        )
    report.metrics["git"] = gi
