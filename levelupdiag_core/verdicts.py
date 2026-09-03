from __future__ import annotations

VERDICTS = (
    "PASS", "WARN", "FAIL", "SKIP", "BLOCKED", "PARTIAL",
    "ERROR", "INFRA_ERROR", "CONFIG_ERROR",
)

RANK = {
    "PASS": 0,
    "WARN": 1,
    "SKIP": 2,
    "PARTIAL": 3,
    "BLOCKED": 4,
    "INFRA_ERROR": 5,
    "FAIL": 6,
    "ERROR": 7,
    "CONFIG_ERROR": 8,
}


def worst(verdicts):
    vals = [v for v in verdicts if v in RANK]
    return max(vals, key=lambda v: RANK[v]) if vals else "PASS"


def level_verdict(findings, default="PASS"):
    vals = [f.get("verdict", "PASS") for f in findings]
    return worst(vals) if vals else default


def campaign_verdict(level_results, required_map):
    if not level_results:
        return "CONFIG_ERROR"
    # Tool/config errors are never accepted as target success.
    if any(r.get("verdict") in {"CONFIG_ERROR", "ERROR"} for r in level_results):
        return "ERROR"
    if any(r.get("verdict") == "FAIL" for r in level_results):
        return "FAIL"
    # Required evidence that could not be established blocks completion.
    for r in level_results:
        if required_map.get(r.get("level_id"), False) and r.get("verdict") in {
            "SKIP", "BLOCKED", "PARTIAL", "INFRA_ERROR"
        }:
            return "BLOCKED"
    if any(r.get("verdict") in {"BLOCKED", "PARTIAL", "INFRA_ERROR"} for r in level_results):
        return "WARN"
    if any(r.get("verdict") == "WARN" for r in level_results):
        return "WARN"
    return "PASS"


def exit_code(verdict):
    if verdict in {"PASS", "WARN"}: return 0
    if verdict == "FAIL": return 10
    if verdict in {"SKIP", "BLOCKED", "PARTIAL"}: return 20
    return 30
