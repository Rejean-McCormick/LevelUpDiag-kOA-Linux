from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from levels.koali_final_support import collect_koali_final_findings

ROOT = Path(__file__).resolve().parents[1]


class KoaliFinalDeltaTests(unittest.TestCase):
    def _fixture(self):
        tmp = tempfile.TemporaryDirectory()
        mycode = Path(tmp.name)
        koali = mycode / "kOA-Linux" / "koali-spaces"
        koali.mkdir(parents=True)
        cfg = json.loads((ROOT / "levelupdiag.config.json").read_text(encoding="utf-8"))
        cfg["_tool_root"] = str(mycode / "kOA-Linux" / "LevelUpDiag-Koali")
        cfg["koali_system"]["root"] = str(koali)

        products = []
        for product_id, policy in cfg["koali_final"]["required_products"].items():
            products.append({"id": product_id, "requiredForBootstrap": True, "affectsShellState": policy["affects_shell_state"]})
        sources = [
            {"id": source_id, "requiredForBootstrap": True, "referenceOnly": False, "integrationMode": "qualified"}
            for source_id in cfg["koali_final"]["required_sources"]
        ]
        sources.append({"id": "kristal_framework", "referenceOnly": True, "integrationMode": "reference_only"})
        (koali / "config").mkdir()
        (koali / "config" / "ecosystem.catalog.json").write_text(json.dumps({"products": products, "sources": sources}), encoding="utf-8")

        for product_id, spec in cfg["koali_final"]["owner_contracts"].items():
            path = mycode / Path(spec["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            surface = {"mode": "headless"} if spec["surface"] == "headless" else {"embedBase": "http://127.0.0.1:9999"}
            path.write_text(json.dumps({"productId": product_id, "surface": surface, "probes": [{"id": "ready", "required": True, "url": "http://127.0.0.1:9999/ready"}]}), encoding="utf-8")

        script = koali / "scripts" / "bootstrap-koali.ps1"
        script.parent.mkdir()
        script.write_text("\n".join(cfg["koali_final"]["bootstrap_contract_tokens"]), encoding="utf-8")
        status = koali / ".koali-dev" / "bootstrap" / "bootstrap-status.json"
        status.parent.mkdir(parents=True)
        status.write_text(json.dumps({
            "checkOnly": False,
            "mycode": str(mycode),
            "events": [{"name": name, "state": "ready"} for name in cfg["koali_final"]["required_bootstrap_events"]],
        }), encoding="utf-8")

        engine = mycode / "kOA_Mediatheque" / "mediatheque"
        instance = mycode / "kOA_Mediatheque" / "mediatheque-blank"
        engine.mkdir(parents=True, exist_ok=True)
        (instance / "01_DB").mkdir(parents=True)
        (instance / "mediatheque.instance.toml").write_text("[instance]\nname='blank'\n", encoding="utf-8")
        db = instance / "01_DB" / "koa_mediatheque.sqlite"
        with sqlite3.connect(db) as conn:
            conn.execute("create table schema_meta (key text primary key, value text not null)")
            conn.execute("insert into schema_meta(key,value) values ('schema_version','4')")

        for marker in cfg["koali_final"]["launcher_markers"]:
            p = koali / marker
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        (koali / "launcher").mkdir(exist_ok=True)
        (koali / "launcher" / "launcher-config.json").write_text(json.dumps({"reservedPorts": cfg["koali_final"]["expected_reserved_ports"]}), encoding="utf-8")
        return tmp, cfg

    def test_complete_final_delta_fixture_has_no_failures(self):
        tmp, cfg = self._fixture()
        self.addCleanup(tmp.cleanup)
        findings, _ = collect_koali_final_findings(cfg)
        bad = [item for item in findings if item["verdict"] in {"FAIL", "BLOCKED", "ERROR", "INFRA_ERROR", "CONFIG_ERROR"}]
        self.assertEqual(bad, [])

    def test_check_only_bootstrap_is_not_accepted_as_final_evidence(self):
        tmp, cfg = self._fixture()
        self.addCleanup(tmp.cleanup)
        koali = Path(cfg["koali_system"]["root"])
        status = koali / ".koali-dev" / "bootstrap" / "bootstrap-status.json"
        value = json.loads(status.read_text())
        value["checkOnly"] = True
        status.write_text(json.dumps(value), encoding="utf-8")
        findings, _ = collect_koali_final_findings(cfg)
        bootstrap = next(item for item in findings if item["id"] == "n14.bootstrap.status")
        self.assertEqual(bootstrap["verdict"], "FAIL")

    def test_kristal_must_stay_reference_only(self):
        tmp, cfg = self._fixture()
        self.addCleanup(tmp.cleanup)
        koali = Path(cfg["koali_system"]["root"])
        catalog_path = koali / "config" / "ecosystem.catalog.json"
        catalog = json.loads(catalog_path.read_text())
        kristal = next(item for item in catalog["sources"] if item["id"] == "kristal_framework")
        kristal["requiredForBootstrap"] = True
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
        findings, _ = collect_koali_final_findings(cfg)
        boundary = next(item for item in findings if item["id"] == "n14.catalog.kristal_boundary")
        self.assertEqual(boundary["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
