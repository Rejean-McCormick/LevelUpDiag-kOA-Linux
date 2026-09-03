from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from levelupdiag_core.manifest import load_manifest

EXPECTED = [f"N{i:02d}" for i in range(12)]
REQUIRED_COMMANDS = {"docs", "contracts", "components", "integrations", "security", "offline", "system"}


def run(cfg, report):
    tool = Path(cfg["_tool_root"])
    report.add("diagnostics.python.version", "PASS" if sys.version_info >= (3,10) else "CONFIG_ERROR", "diagnostics",
               f"Python {sys.version.split()[0]} is {'supported' if sys.version_info >= (3,10) else 'unsupported'}.",
               recommendation=None if sys.version_info >= (3,10) else "Use Python 3.10 or newer.")
    manifest = load_manifest(tool)
    ordered = [x["id"] for x in sorted(manifest["levels"], key=lambda x:(x.get("order",0),x["id"]))]
    report.add("koali.sequence.manifest", "PASS" if ordered == EXPECTED else "CONFIG_ERROR", "diagnostics",
               "Koali diagnostic sequence is intact." if ordered == EXPECTED else "Koali diagnostic sequence differs from the expected N00-N11 order.", evidence=ordered)
    parallel = [x["id"] for x in manifest["levels"] if x.get("parallel_safe", True)]
    report.add("koali.sequence.serial", "PASS" if not parallel else "CONFIG_ERROR", "diagnostics",
               "All Koali levels are forced to serial execution." if not parallel else "One or more Koali levels permit parallel execution.", evidence=parallel or {"serial":True})
    missing_modules = [x["module"] for x in manifest["levels"] if importlib.util.find_spec(x["module"]) is None]
    report.add("diagnostics.level_modules.available", "PASS" if not missing_modules else "CONFIG_ERROR", "diagnostics",
               "All declared level modules are importable." if not missing_modules else "Declared level modules are missing.", evidence=missing_modules or {"count":len(manifest["levels"])})
    commands = cfg.get("commands", {})
    missing_keys = sorted(REQUIRED_COMMANDS - set(commands))
    report.add("koali.commands.contract", "PASS" if not missing_keys else "CONFIG_ERROR", "configuration",
               "Koali command configuration contract is present." if not missing_keys else "Koali command configuration keys are missing.", evidence=missing_keys or sorted(REQUIRED_COMMANDS))
    schema_dir = tool / "schemas"
    absent = [p.name for p in (schema_dir/"report.schema.json", schema_dir/"campaign-summary.schema.json") if not p.exists()]
    report.add("diagnostics.schemas.present", "PASS" if not absent else "CONFIG_ERROR", "diagnostics",
               "Required result schemas are present." if not absent else "Required result schemas are missing.", evidence=absent or {"count":2})
