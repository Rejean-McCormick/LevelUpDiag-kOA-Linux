from __future__ import annotations

import importlib
import traceback
from pathlib import Path
from .config import load_config
from .manifest import load_manifest, level_map
from .modes import normalize_mode
from .report import Report
from .util import write_json


def run_worker(tool_root: Path, level_id: str, run_id: str, output: Path, target_override=None, mode="debug"):
    manifest = load_manifest(tool_root)
    meta = level_map(manifest).get(level_id)
    if not meta:
        raise RuntimeError(f"Unknown level {level_id}")
    cfg = load_config(tool_root, target_override)
    cfg["_mode"] = normalize_mode(mode, str(cfg.get("default_mode", "debug")))
    report = Report(level_id, meta["name"], meta.get("purpose", ""), cfg["_target_root"], run_id)
    report.metrics["diagnostic_mode"] = cfg["_mode"]
    try:
        module = importlib.import_module(meta["module"])
        module.run(cfg, report)
        data = report.to_dict()
    except Exception as e:
        report.add(
            "diagnostics.level.exception", "ERROR", "diagnostics",
            f"Unhandled exception inside {level_id}",
            evidence=f"{type(e).__name__}: {e}",
            recommendation="Inspect the level traceback artifact and fix the diagnostics code."
        )
        tb = traceback.format_exc()
        tb_path = output.parent / "traceback.txt"
        tb_path.parent.mkdir(parents=True, exist_ok=True)
        tb_path.write_text(tb, encoding="utf-8")
        report.artifact("traceback", tb_path, "Unhandled level exception")
        data = report.to_dict(override_verdict="ERROR")
    data["diagnostic_mode"] = cfg["_mode"]
    write_json(output, data)
    return data
