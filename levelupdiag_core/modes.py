from __future__ import annotations

VALID_MODES = ("debug", "validation", "release")

_DEFAULTS = {
    "debug": {
        "protect_tracked_files": False,
        "dependency_blocking_verdicts": [],
        "campaign_policy": "diagnostic",
    },
    "validation": {
        "protect_tracked_files": False,
        "dependency_blocking_verdicts": ["BLOCKED", "ERROR", "INFRA_ERROR", "CONFIG_ERROR"],
        "campaign_policy": "validation",
    },
    "release": {
        "protect_tracked_files": True,
        "dependency_blocking_verdicts": ["BLOCKED", "ERROR", "INFRA_ERROR", "CONFIG_ERROR"],
        "campaign_policy": "release",
    },
}


def normalize_mode(value: str | None, default: str = "debug") -> str:
    mode = (value or default or "debug").strip().casefold()
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported diagnostic mode: {mode}")
    return mode


def policy_for(cfg: dict, mode: str) -> dict:
    mode = normalize_mode(mode)
    policy = dict(_DEFAULTS[mode])
    configured = cfg.get("modes", {}).get(mode, {})
    if isinstance(configured, dict):
        policy.update(configured)
    blockers = policy.get("dependency_blocking_verdicts", [])
    if not isinstance(blockers, list) or not all(isinstance(x, str) for x in blockers):
        raise ValueError(f"modes.{mode}.dependency_blocking_verdicts must be a string list")
    policy["dependency_blocking_verdicts"] = set(blockers)
    policy["protect_tracked_files"] = bool(policy.get("protect_tracked_files", False))
    return policy
