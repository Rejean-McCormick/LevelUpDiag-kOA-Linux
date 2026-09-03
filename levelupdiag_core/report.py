from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from . import REPORT_SCHEMA, VERSION
from .util import utc_now, write_json
from .verdicts import level_verdict

@dataclass
class Report:
    level_id: str
    level_name: str
    purpose: str
    target_root: str
    run_id: str
    started_at: str = field(default_factory=utc_now)
    findings: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def add(self, finding_id, verdict, category, message, *, evidence=None,
            recommendation=None, path=None, data=None):
        item = {
            "id": finding_id,
            "verdict": verdict,
            "category": category,
            "message": message,
        }
        if evidence is not None: item["evidence"] = evidence
        if recommendation is not None: item["recommendation"] = recommendation
        if path is not None: item["path"] = path
        if data is not None: item["data"] = data
        self.findings.append(item)
        return item

    def artifact(self, kind, path, description=None):
        a = {"kind": kind, "path": str(path)}
        if description: a["description"] = description
        self.artifacts.append(a)

    def to_dict(self, ended_at=None, override_verdict=None):
        return {
            "schema": REPORT_SCHEMA,
            "standard": "LevelUpDiag",
            "standard_version": VERSION,
            "run_id": self.run_id,
            "level_id": self.level_id,
            "level_name": self.level_name,
            "purpose": self.purpose,
            "target_repo_root": self.target_root,
            "started_at": self.started_at,
            "ended_at": ended_at or utc_now(),
            "verdict": override_verdict or level_verdict(self.findings),
            "findings": self.findings,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
        }

    def write(self, path: Path, override_verdict=None):
        data = self.to_dict(override_verdict=override_verdict)
        write_json(path, data)
        return data
