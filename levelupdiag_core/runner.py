from __future__ import annotations

import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import SUMMARY_SCHEMA, VERSION
from .config import load_config
from .manifest import load_manifest, resolve_selection
from .modes import normalize_mode, policy_for
from .util import read_json, utc_now, write_json
from .verdicts import campaign_verdict, execution_verdict, exit_code, testability
from .vcs import git_info

FINAL = {"PASS","WARN","FAIL","SKIP","BLOCKED","PARTIAL","ERROR","INFRA_ERROR","CONFIG_ERROR"}


def make_run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def _result_for_blocked(meta, run_id, target, deps):
    now = utc_now()
    return {
        "schema":"levelupdiag.report.v2","standard":"LevelUpDiag","standard_version":VERSION,
        "run_id":run_id,"level_id":meta["id"],"level_name":meta["name"],
        "purpose":meta.get("purpose", ""),"target_repo_root":str(target),
        "started_at":now,"ended_at":now,"verdict":"BLOCKED",
        "findings":[{"id":"dependencies.required.blocked","verdict":"BLOCKED","category":"dependency",
                     "message":"A required diagnostic dependency did not produce usable evidence in this mode.",
                     "evidence":{"dependencies":deps}}],
        "artifacts":[],"metrics":{}
    }


def _selection_mode(manifest: dict, selection: str, requested_mode: str | None, cfg: dict) -> str:
    if requested_mode:
        return normalize_mode(requested_mode)
    campaign = manifest.get("campaigns", {}).get(selection)
    campaign_mode = campaign.get("mode") if isinstance(campaign, dict) else None
    return normalize_mode(campaign_mode, str(cfg.get("default_mode", "debug")))


def run_campaign(tool_root: Path, selection: str, target_override=None, jobs=None, fail_fast=None, mode=None):
    manifest = load_manifest(tool_root)
    cfg = load_config(tool_root, target_override)
    effective_mode = _selection_mode(manifest, selection, mode, cfg)
    policy = policy_for(cfg, effective_mode)
    cfg["_mode"] = effective_mode
    campaign_meta = manifest.get("campaigns", {}).get(selection, {}) if isinstance(manifest.get("campaigns", {}), dict) else {}
    qualification_scope = str(campaign_meta.get("scope", "ad_hoc" if selection not in manifest.get("campaigns", {}) else "full_target"))
    deferred_subsystems = [str(x) for x in campaign_meta.get("deferred_subsystems", []) if str(x)] if isinstance(campaign_meta, dict) else []
    qualification_cfg = cfg.get("qualification", {}) if isinstance(cfg.get("qualification", {}), dict) else {}
    configured_states = qualification_cfg.get("deferred_subsystems", {})
    deferred_subsystem_states = (
        {name: str(configured_states.get(name, "deferred")) for name in deferred_subsystems}
        if isinstance(configured_states, dict) else {}
    )
    levels = resolve_selection(manifest, selection)
    target = Path(cfg["_target_root"])
    control = Path(cfg["_control_root"])
    run_id = make_run_id()
    run_root = control / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    effective_config = {k:v for k,v in cfg.items() if not k.startswith("_")}
    effective_config["diagnostic_mode"] = effective_mode
    write_json(run_root / "effective_config.json", effective_config)

    protect = policy["protect_tracked_files"]
    before_vcs = git_info(target) if protect else None
    dependency_blockers = policy["dependency_blocking_verdicts"]
    max_jobs = int(jobs or cfg.get("execution",{}).get("max_parallel", 4) or 1)
    max_jobs = max(1, min(max_jobs, 16))
    ff = cfg.get("execution",{}).get("fail_fast", False) if fail_fast is None else fail_fast

    by_id = {m["id"]:m for m in levels}
    pending = set(by_id)
    results = {}
    active = {}
    pool = ThreadPoolExecutor(max_workers=max_jobs)

    def launch(meta):
        level_dir = run_root / "levels" / meta["id"]
        level_dir.mkdir(parents=True, exist_ok=True)
        out = level_dir / "result.json"
        cmd = [
            sys.executable, str(tool_root / "levelupdiag.py"), "_worker",
            "--level", meta["id"], "--run-id", run_id, "--output", str(out),
            "--target", str(target), "--mode", effective_mode,
        ]
        timeout = int(meta.get("timeout_seconds") or cfg.get("execution",{}).get("default_timeout_seconds",120))
        started_mono = time.monotonic()
        try:
            cp = subprocess.run(
                cmd, cwd=str(target), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
                shell=False, check=False,
            )
            if out.exists():
                data = read_json(out)
            else:
                verdict = "INFRA_ERROR" if cp.returncode != 0 else "ERROR"
                now = utc_now()
                data = {
                    "schema":"levelupdiag.report.v2","standard":"LevelUpDiag","standard_version":VERSION,
                    "run_id":run_id,"level_id":meta["id"],"level_name":meta["name"],"purpose":meta.get("purpose", ""),
                    "target_repo_root":str(target),"started_at":now,"ended_at":now,"verdict":verdict,
                    "findings":[{"id":"diagnostics.worker.missing_result","verdict":verdict,"category":"diagnostics",
                                 "message":"Worker did not produce a result file.",
                                 "evidence":{"return_code":cp.returncode,"stdout_tail":cp.stdout[-4000:],"stderr_tail":cp.stderr[-4000:]}}],
                    "artifacts":[],"metrics":{},
                }
                write_json(out, data)
            data["diagnostic_mode"] = effective_mode
            data.setdefault("metrics", {})["worker_duration_seconds"] = round(time.monotonic()-started_mono, 3)
            write_json(out, data)
            return data
        except subprocess.TimeoutExpired:
            now = utc_now()
            data = {
                "schema":"levelupdiag.report.v2","standard":"LevelUpDiag","standard_version":VERSION,
                "run_id":run_id,"level_id":meta["id"],"level_name":meta["name"],"purpose":meta.get("purpose", ""),
                "target_repo_root":str(target),"started_at":now,"ended_at":now,"verdict":"INFRA_ERROR",
                "diagnostic_mode":effective_mode,
                "findings":[{"id":"diagnostics.worker.timeout","verdict":"INFRA_ERROR","category":"diagnostics",
                             "message":f"Level exceeded its {timeout}s timeout.",
                             "recommendation":"Increase the timeout only if the level is expected to require more time."}],
                "artifacts":[],"metrics":{"worker_duration_seconds":round(time.monotonic()-started_mono,3)},
            }
            write_json(out, data)
            return data

    try:
        while pending or active:
            for lid, fut in list(active.items()):
                if fut.done():
                    results[lid] = fut.result()
                    del active[lid]

            if ff and any(r.get("verdict") in {"FAIL","ERROR","CONFIG_ERROR"} for r in results.values()):
                for lid in list(pending):
                    meta = by_id[lid]
                    results[lid] = _result_for_blocked(meta, run_id, target, {"fail_fast":"campaign stopped"})
                    pending.remove(lid)
                continue

            ready = []
            for lid in list(pending):
                meta = by_id[lid]
                deps = [d for d in meta.get("depends_on",[]) if d in by_id]
                if all(d in results for d in deps):
                    bad = {
                        d: results[d].get("verdict")
                        for d in deps
                        if results[d].get("verdict") in dependency_blockers
                    }
                    if bad:
                        results[lid] = _result_for_blocked(meta, run_id, target, bad)
                        pending.remove(lid)
                    else:
                        ready.append(meta)
            ready.sort(key=lambda x:(x.get("order",0),x["id"]))

            exclusive = next((m for m in ready if not m.get("parallel_safe", True)), None)
            launched = False
            if exclusive and not active:
                active[exclusive["id"]] = pool.submit(launch, exclusive)
                pending.remove(exclusive["id"])
                launched = True
            elif not exclusive:
                capacity = max_jobs - len(active)
                for meta in ready[:max(0, capacity)]:
                    active[meta["id"]] = pool.submit(launch, meta)
                    pending.remove(meta["id"])
                    launched = True

            if not launched and active:
                time.sleep(0.04)
            elif not launched and pending and not active:
                for lid in list(pending):
                    results[lid] = _result_for_blocked(by_id[lid], run_id, target, {"scheduler":"no runnable dependency state"})
                    pending.remove(lid)
    finally:
        pool.shutdown(wait=True)

    ordered = [results[m["id"]] for m in levels]
    required_map = {m["id"]:bool(m.get("required",False)) for m in levels}
    verdict = campaign_verdict(ordered, required_map, effective_mode)

    after_vcs = git_info(target) if before_vcs is not None else None
    if not protect:
        protection = {
            "enabled": False,
            "verdict": "SKIP",
            "message": f"Tracked Git-state protection is outside {effective_mode.upper()} policy.",
        }
    elif not before_vcs.get("repository") or not after_vcs or not after_vcs.get("repository"):
        protection = {
            "enabled": True,
            "verdict": "WARN",
            "message": "Tracked VCS state protection could not verify a Git repository before and after diagnostics.",
            "before": before_vcs,
            "after": after_vcs,
        }
    elif before_vcs.get("tracked_status") != after_vcs.get("tracked_status"):
        protection = {
            "enabled": True,
            "verdict": "ERROR",
            "message": "Tracked VCS state changed during diagnostics.",
            "before": before_vcs,
            "after": after_vcs,
        }
        verdict = "ERROR"
    else:
        protection = {
            "enabled": True,
            "verdict": "PASS",
            "message": "Tracked VCS state was unchanged during diagnostics.",
            "before": before_vcs,
            "after": after_vcs,
        }

    counts = {v:0 for v in FINAL}
    for r in ordered:
        counts[r.get("verdict","ERROR")] = counts.get(r.get("verdict","ERROR"),0)+1

    exec_verdict = execution_verdict(ordered)
    summary = {
        "schema":SUMMARY_SCHEMA,"standard":"LevelUpDiag","standard_version":VERSION,
        "run_id":run_id,"selection":selection,"diagnostic_mode":effective_mode,
        "qualification_scope":qualification_scope,"deferred_subsystems":deferred_subsystems,
        "deferred_subsystem_states":deferred_subsystem_states,
        "target_repo_root":str(target),"started_at":started,"ended_at":utc_now(),
        "verdict":verdict,"execution_verdict":exec_verdict,"testability":testability(ordered),
        "conformance_verdict":"NOT_EVALUATED" if effective_mode == "debug" else verdict,
        "counts":counts,
        "expected_levels":[m["id"] for m in levels],
        "required_levels":[m["id"] for m in levels if m.get("required")],
        "levels":[{"id":r["level_id"],"name":r["level_name"],"verdict":r["verdict"],
                   "result":str((run_root/"levels"/r["level_id"]/"result.json").relative_to(run_root))} for r in ordered],
        "target_protection":protection,
    }
    write_json(run_root / "summary.json", summary)
    txt = [
        f"LevelUpDiag {selection} [{effective_mode.upper()}] - {verdict}",
        f"Run: {run_id}", f"Target: {target}",
        f"Diagnostic execution: {exec_verdict}",
        f"System testability: {summary['testability']}",
        f"Qualification scope: {qualification_scope}",
        f"Deferred subsystems: {', '.join(deferred_subsystems) if deferred_subsystems else 'none'}",
        f"Subsystem states: {', '.join(f'{name}={state}' for name, state in deferred_subsystem_states.items()) if deferred_subsystem_states else 'none'}",
        f"Conformance: {summary['conformance_verdict']}", "",
    ]
    txt += [f"{r['level_id']:>3}  {r['verdict']:<12} {r['level_name']}" for r in ordered]
    if protection.get("verdict") == "ERROR":
        txt += ["", "ERROR: tracked VCS state changed during diagnostics."]
    (run_root / "summary.txt").write_text("\n".join(txt)+"\n", encoding="utf-8")

    latest = control / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    write_json(latest / "summary.json", summary)
    for r in ordered:
        src = run_root / "levels" / r["level_id"] / "result.json"
        dst = latest / r["level_id"] / "result.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return summary, exit_code(verdict), run_root
