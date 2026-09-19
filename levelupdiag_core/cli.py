from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .manifest import ManifestError, load_manifest
from .modes import VALID_MODES
from .runner import run_campaign
from .util import read_json
from .worker import run_worker


def parser():
    p = argparse.ArgumentParser(prog="levelupdiag", description="LevelUpDiag specialization for the live Koali product system and legacy kOA-Linux stabilization")
    p.add_argument("--target", help="Target repository root (default from configuration)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="Validate LevelUpDiag setup and target resolution")
    sub.add_parser("list", help="List levels and campaigns")
    sub.add_parser("show-config", help="Print effective configuration")
    r = sub.add_parser("run", help="Run a campaign or level")
    r.add_argument("selection", nargs="?", default="koali-system")
    r.add_argument("--mode", choices=VALID_MODES, help="Override campaign policy mode")
    r.add_argument("--jobs", type=int, help="Maximum parallel level workers")
    r.add_argument("--fail-fast", action="store_true")
    v = sub.add_parser("verify-run", help="Verify a campaign summary structure")
    v.add_argument("summary")
    w = sub.add_parser("_worker", help=argparse.SUPPRESS)
    w.add_argument("--level", required=True)
    w.add_argument("--run-id", required=True)
    w.add_argument("--output", required=True)
    w.add_argument("--target", required=True, dest="worker_target")
    w.add_argument("--mode", choices=VALID_MODES, default="debug")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    tool_root = Path(__file__).resolve().parents[1]
    try:
        if args.cmd == "_worker":
            data = run_worker(tool_root, args.level, args.run_id, Path(args.output), args.worker_target, args.mode)
            return 0 if data.get("verdict") in {"PASS","WARN","SKIP","PARTIAL"} else 1
        manifest = load_manifest(tool_root)
        if args.cmd == "doctor":
            cfg = load_config(tool_root, args.target)
            print("LevelUpDiag doctor: PASS")
            print(f"tool_root:   {tool_root}")
            print(f"target_root: {cfg['_target_root']}")
            print(f"control_dir: {cfg['_control_root']}")
            print(f"default_mode:{cfg.get('default_mode', 'debug')}")
            print(f"levels:      {len(manifest['levels'])}")
            return 0
        if args.cmd == "list":
            print("Levels:")
            for x in sorted(manifest["levels"], key=lambda y:(y.get("order",0),y["id"])):
                req = "required" if x.get("required") else "optional"
                print(f"  {x['id']}  {x['name']} [{req}] [{x.get('category','')}]" )
            print("Campaigns:")
            for name, c in manifest.get("campaigns",{}).items():
                print(f"  {name} [{c.get('mode','debug')}]: {', '.join(c.get('levels',[]))}")
            return 0
        if args.cmd == "show-config":
            cfg = load_config(tool_root, args.target)
            print(json.dumps({k:v for k,v in cfg.items() if not k.startswith('_')}, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "run":
            summary, code, run_root = run_campaign(
                tool_root, args.selection, args.target, args.jobs, args.fail_fast, args.mode
            )
            print(f"LevelUpDiag {args.selection} [{summary['diagnostic_mode'].upper()}]: {summary['verdict']}")
            print(f"  Diagnostic execution: {summary['execution_verdict']}")
            print(f"  System testability:    {summary['testability']}")
            print(f"  Qualification scope:  {summary.get('qualification_scope', 'ad_hoc')}")
            deferred = summary.get('deferred_subsystems', [])
            print(f"  Deferred subsystems:   {', '.join(deferred) if deferred else 'none'}")
            states = summary.get('deferred_subsystem_states', {})
            if isinstance(states, dict) and states:
                print("  Subsystem states:      " + ", ".join(f"{name}={state}" for name, state in states.items()))
            print(f"  Conformance:           {summary['conformance_verdict']}")
            for row in summary["levels"]:
                print(f"  {row['id']}  {row['verdict']:<12} {row['name']}")
            print(f"Report: {run_root / 'summary.json'}")
            return code
        if args.cmd == "verify-run":
            p = Path(args.summary)
            d = read_json(p)
            required = {"schema","run_id","selection","verdict","expected_levels","levels"}
            missing = sorted(required - set(d))
            if missing:
                print("INVALID: missing " + ", ".join(missing)); return 30
            if d.get("schema") != "levelupdiag.campaign-summary.v2":
                print("INVALID: unsupported schema"); return 30
            ids = [x.get("id") for x in d.get("levels",[])]
            if ids != d.get("expected_levels"):
                print("INVALID: levels do not match expected_levels"); return 30
            print("VALID"); return 0
        return 64
    except (ConfigError, ManifestError, OSError, ValueError) as e:
        print(f"LevelUpDiag error: {e}", file=sys.stderr)
        return 30
