from pathlib import Path
import tempfile
import unittest
from levels.koali_support import missing_python_modules, referenced_gate_reports

class SupportTests(unittest.TestCase):
    def test_missing_module_detection(self):
        text = "ModuleNotFoundError: No module named 'alpha.beta'\nModuleNotFoundError: No module named \"gamma\""
        self.assertEqual(missing_python_modules(text), ["alpha.beta", "gamma"])

    def test_referenced_report_is_bounded_to_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / "koa-ci-evidence" / "security-gate-report.json"
            good.parent.mkdir()
            good.write_text('{"password":"supersecret"}', encoding="utf-8")
            outside = root.parent / "koa-ci-evidence" / "outside-gate-report.json"
            outside.parent.mkdir(exist_ok=True)
            outside.write_text('{"x":1}', encoding="utf-8")
            cfg = {"_target_root":str(root), "koa":{}, "redaction":{"enabled":True,"replacement":"<REDACTED>"}}
            text = f"report={good}\nreport={outside}\n"
            items = referenced_gate_reports(cfg, text)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["path"], "koa-ci-evidence/security-gate-report.json")
            self.assertIn("<REDACTED>", items[0]["content_tail"])
            self.assertNotIn("supersecret", items[0]["content_tail"])

if __name__ == "__main__": unittest.main()
