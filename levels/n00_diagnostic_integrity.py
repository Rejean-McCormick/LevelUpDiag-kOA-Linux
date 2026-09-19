from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from levelupdiag_core.manifest import load_manifest
from levelupdiag_core.modes import VALID_MODES

EXPECTED = [f"N{i:02d}" for i in range(14)]
REQUIRED_COMMANDS = {"docs", "contracts", "components", "integrations", "security", "offline", "system"}


def run(cfg, report):
    tool = Path(cfg["_tool_root"])
    report.add("diagnostics.python.version", "PASS" if sys.version_info >= (3,10) else "CONFIG_ERROR", "diagnostics",
               f"Python {sys.version.split()[0]} is {'supported' if sys.version_info >= (3,10) else 'unsupported'}.",
               recommendation=None if sys.version_info >= (3,10) else "Use Python 3.10 or newer.")
    manifest = load_manifest(tool)
    ordered = [x["id"] for x in sorted(manifest["levels"], key=lambda x:(x.get("order",0),x["id"]))]
    report.add("koali.sequence.manifest", "PASS" if ordered == EXPECTED else "CONFIG_ERROR", "diagnostics",
               "Koali diagnostic sequence is intact." if ordered == EXPECTED else "Koali diagnostic sequence differs from the expected N00-N13 order.", evidence=ordered)
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
    campaigns = manifest.get("campaigns", {})
    missing_modes = [m for m in VALID_MODES if m not in {c.get("mode") for c in campaigns.values() if isinstance(c, dict)}]
    report.add("diagnostics.modes.present", "PASS" if not missing_modes else "CONFIG_ERROR", "diagnostics",
               "DEBUG, VALIDATION, and RELEASE policies are represented in the campaign manifest." if not missing_modes else "One or more diagnostic modes are missing from campaigns.", evidence=missing_modes or list(VALID_MODES))
    debug_levels = set(campaigns.get("debug", {}).get("levels", []))
    formal = sorted(debug_levels & {"N02", "N03", "N11"})
    report.add("diagnostics.debug.decoupled", "PASS" if not formal else "CONFIG_ERROR", "diagnostics",
               "Primary DEBUG is decoupled from repository/documentation/release formalities." if not formal else "Primary DEBUG still selects formal conformance levels.", evidence=formal or sorted(debug_levels))
    koali_system = cfg.get("koali_system", {})
    system_ok = isinstance(koali_system, dict) and bool(koali_system.get("root")) and isinstance(koali_system.get("expected_products"), list)
    report.add("diagnostics.koali_system.config", "PASS" if system_ok else "CONFIG_ERROR", "configuration",
               "Live Koali system diagnostic configuration is present." if system_ok else "Live Koali system diagnostic configuration is missing or invalid.")
    store = cfg.get("store", {})
    store_ok = isinstance(store, dict) and isinstance(store.get("root"), str) and bool(store.get("root")) and isinstance(store.get("runtime_checks"), bool)
    report.add("diagnostics.store.config", "PASS" if store_ok else "CONFIG_ERROR", "configuration",
               "Store source/session diagnostic configuration is valid." if store_ok else "Store diagnostic configuration is missing or invalid.")
    schema_dir = tool / "schemas"
    absent = [p.name for p in (schema_dir/"report.schema.json", schema_dir/"campaign-summary.schema.json") if not p.exists()]
    report.add("diagnostics.schemas.present", "PASS" if not absent else "CONFIG_ERROR", "diagnostics",
               "Required result schemas are present." if not absent else "Required result schemas are missing.", evidence=absent or {"count":2})
