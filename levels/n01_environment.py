from __future__ import annotations
import platform
import sys
from pathlib import Path
from levelupdiag_core.commands import which


def _available(name: str):
    if name.casefold() in {"python", "python3", "py"}:
        return True, sys.executable
    return (bool(which(name)), which(name))


def run(cfg, report):
    target = Path(cfg["_target_root"])
    report.add("koali.target.root", "PASS" if target.is_dir() else "CONFIG_ERROR", "environment", "kOA-Linux target repository root is available.", path=str(target))
    report.add("koali.runtime", "PASS", "environment", "Runtime context detected.", evidence={"platform":platform.platform(),"python":sys.version.split()[0],"executable":sys.executable})
    toolchain = cfg.get("toolchain", {})
    for required, bucket in ((True, "required"), (False, "optional")):
        for name in toolchain.get(bucket, []):
            ok, path = _available(str(name))
            verdict = "PASS" if ok else ("BLOCKED" if required else "WARN")
            report.add(f"koali.tool.{name}", verdict, "environment",
                       f"Tool '{name}' is available." if ok else f"Tool '{name}' is not available on PATH.", evidence=path,
                       recommendation=None if ok else (f"Install or expose '{name}' before running levels that require it." if required else f"Install '{name}' if optional Koali validations need it."))
