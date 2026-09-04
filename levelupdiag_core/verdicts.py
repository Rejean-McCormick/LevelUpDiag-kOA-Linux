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


def campaign_verdict(level_results, required_map, mode="validation"):
    if not level_results:
        return "ERROR"

    values = [r.get("verdict", "ERROR") for r in level_results]

    # DEBUG answers: "did the diagnostic run, and did it find anything worth attention?"
    # Target failures, unavailable prerequisites, repository formalities, and configuration
    # gaps remain visible at their own level but do not turn the whole debug run into BLOCKED.
    if mode == "debug":
        if any(v in {"ERROR", "INFRA_ERROR"} for v in values):
            return "ERROR"
        if any(v != "PASS" for v in values):
            return "WARN"
        return "PASS"

    # VALIDATION/RELEASE preserve strict evidence semantics.
    if any(v in {"CONFIG_ERROR", "ERROR"} for v in values):
        return "ERROR"
    if any(v == "FAIL" for v in values):
        return "FAIL"
    for r in level_results:
        if required_map.get(r.get("level_id"), False) and r.get("verdict") in {
            "SKIP", "BLOCKED", "PARTIAL", "INFRA_ERROR"
        }:
            return "BLOCKED"
    if any(v in {"BLOCKED", "PARTIAL", "INFRA_ERROR"} for v in values):
        return "WARN"
    if any(v == "WARN" for v in values):
        return "WARN"
    return "PASS"


def execution_verdict(level_results):
    return "ERROR" if any(r.get("verdict") in {"ERROR", "INFRA_ERROR"} for r in level_results) else "PASS"


def testability(level_results):
    unavailable = {"SKIP", "BLOCKED", "PARTIAL", "CONFIG_ERROR", "INFRA_ERROR"}
    return "PARTIAL" if any(r.get("verdict") in unavailable for r in level_results) else "COMPLETE"


def exit_code(verdict):
    if verdict in {"PASS", "WARN"}: return 0
    if verdict == "FAIL": return 10
    if verdict in {"SKIP", "BLOCKED", "PARTIAL"}: return 20
    return 30
