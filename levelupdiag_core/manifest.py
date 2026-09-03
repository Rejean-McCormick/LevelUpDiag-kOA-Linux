from __future__ import annotations

from pathlib import Path
from .util import read_json

class ManifestError(RuntimeError):
    pass


def load_manifest(tool_root: Path):
    path = tool_root / "levelupdiag_manifest.json"
    if not path.exists():
        raise ManifestError(f"Missing manifest: {path}")
    m = read_json(path)
    if m.get("schema") != "levelupdiag.manifest.v2":
        raise ManifestError("Unsupported manifest schema")
    levels = m.get("levels")
    if not isinstance(levels, list) or not levels:
        raise ManifestError("Manifest must declare levels")
    ids = [x.get("id") for x in levels]
    if len(ids) != len(set(ids)) or any(not x for x in ids):
        raise ManifestError("Level IDs must be non-empty and unique")
    known = set(ids)
    for level in levels:
        for dep in level.get("depends_on", []):
            if dep not in known:
                raise ManifestError(f"{level['id']} depends on unknown level {dep}")
    return m


def level_map(manifest):
    return {x["id"]: x for x in manifest["levels"]}


def resolve_selection(manifest, name):
    lm = level_map(manifest)
    if name in lm:
        selected = {name}
    elif name in manifest.get("campaigns", {}):
        selected = set(manifest["campaigns"][name].get("levels", []))
    else:
        raise ManifestError(f"Unknown level or campaign: {name}")
    # Add transitive dependencies.
    changed = True
    while changed:
        changed = False
        for lid in list(selected):
            for dep in lm[lid].get("depends_on", []):
                if dep not in selected:
                    selected.add(dep); changed = True
    return sorted((lm[x] for x in selected), key=lambda x: (x.get("order", 0), x["id"]))
