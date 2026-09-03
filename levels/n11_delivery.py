from __future__ import annotations
import os
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

SIGNATURES = (
    "levelupdiag", "levelupdiag-koali", "levelupdiag_core", ".levelupdiag",
    "levelupdiag_manifest.json", "levelupdiag.config.json", "levelupdiag.config.local.json",
    "run_levelupdiag.bat", "run_levelupdiag.sh", "start_levelupdiag.bat",
)


def _target(cfg):
    raw = os.environ.get("LEVELUPDIAG_DELIVERY_TARGET", "").strip() or str(cfg.get("delivery_target", "")).strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path(cfg["_target_root"]) / p
    return p.resolve(strict=False)


def _match(text):
    parts = [x.casefold() for x in PurePosixPath(text.replace("\\", "/").strip("/")).parts]
    for sig in SIGNATURES:
        if sig.casefold() in parts:
            return sig
    return None


def _scan_dir(target):
    out=[]
    for current, dirs, files in os.walk(target, followlinks=False):
        cur=Path(current)
        for name in [*dirs,*files]:
            rel=(cur/name).relative_to(target).as_posix(); sig=_match(rel)
            if sig: out.append((rel,sig))
    return out


def _scan_zip(target):
    with zipfile.ZipFile(target) as z:
        return [(i.filename, _match(i.filename)) for i in z.infolist() if _match(i.filename)]


def _scan_tar(target):
    with tarfile.open(target, "r:*") as t:
        return [(m.name, _match(m.name)) for m in t if _match(m.name)]


def run(cfg, report):
    target = _target(cfg)
    if target is None:
        report.add("n11.delivery.target.missing", "CONFIG_ERROR", "delivery", "No delivery target is configured.", recommendation="Set delivery_target in levelupdiag.config.local.json or LEVELUPDIAG_DELIVERY_TARGET.")
        return
    if not target.exists():
        report.add("n11.delivery.target.not_found", "CONFIG_ERROR", "delivery", "Configured delivery target does not exist.", path=str(target)); return
    try:
        if target.is_dir(): matches=_scan_dir(target)
        elif target.is_file() and zipfile.is_zipfile(target): matches=_scan_zip(target)
        elif target.is_file() and tarfile.is_tarfile(target): matches=_scan_tar(target)
        else:
            report.add("n11.delivery.target.unsupported", "BLOCKED", "delivery", "Delivery target must be a directory, ZIP, or TAR archive.", path=str(target)); return
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        report.add("n11.delivery.inspection", "INFRA_ERROR", "delivery", "Delivery target could not be inspected.", evidence=f"{type(exc).__name__}: {exc}"); return
    if matches:
        for i,(rel,sig) in enumerate(matches[:100],1):
            report.add(f"n11.delivery.residue.{i:03d}", "FAIL", "delivery", f"LevelUpDiag-Koali residue detected: {rel}", path=rel, evidence={"signature":sig}, recommendation="Remove the diagnostic appendix from delivery staging and rebuild the artifact.")
        if len(matches)>100:
            report.add("n11.delivery.residue.truncated", "WARN", "delivery", "Additional LevelUpDiag residues were detected but not individually listed.", evidence={"total":len(matches)})
    else:
        report.add("n11.delivery.clean", "PASS", "delivery", "No LevelUpDiag-Koali residue detected in the delivery target.", path=str(target))
    report.metrics.update({"delivery_target":str(target),"residue_count":len(matches)})
