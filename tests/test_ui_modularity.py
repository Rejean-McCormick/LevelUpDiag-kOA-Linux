from pathlib import Path
import tempfile
import unittest

from levels.koali_support import collect_ui_modularity_findings


class UiModularityTests(unittest.TestCase):
    def _cfg(self, tool_root: Path, products):
        return {
            "_tool_root": str(tool_root),
            "ui_modularity": {
                "enabled": True,
                "base_root": "..",
                "products": products,
            },
        }

    def test_optional_removed_product_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            tool = workspace / "LevelUpDiag-Koali"
            tool.mkdir()
            findings, metrics = collect_ui_modularity_findings(
                self._cfg(tool, [{"id": "orgo", "root": "orgo", "required": False}])
            )
            self.assertEqual([item["verdict"] for item in findings], ["PASS"])
            self.assertEqual(findings[0]["evidence"]["state"], "absent_optional")
            self.assertEqual(metrics["optional_absent_products"], 1)

    def test_required_removed_product_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            tool = workspace / "LevelUpDiag-Koali"
            tool.mkdir()
            findings, _ = collect_ui_modularity_findings(
                self._cfg(tool, [{"id": "required-ui", "root": "required-ui", "required": True}])
            )
            self.assertEqual(findings[0]["verdict"], "BLOCKED")

    def test_markers_and_private_dependency_scan_pass(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            tool = workspace / "LevelUpDiag-Koali"
            product = workspace / "orgo"
            tool.mkdir()
            (product / "src").mkdir(parents=True)
            (product / "src" / "standalone.tsx").write_text("standalone", encoding="utf-8")
            (product / "src" / "module.ts").write_text("module", encoding="utf-8")
            (product / "package.json").write_text('{"dependencies":{"@koali/ui":"1"}}', encoding="utf-8")
            products = [{
                "id": "orgo",
                "root": "orgo",
                "standalone_markers": ["src/standalone.tsx"],
                "integration_markers": ["src/module.ts"],
                "scan_files": ["package.json"],
                "forbidden_private_ui_tokens": ["@konnaxion/private-ui"],
            }]
            findings, metrics = collect_ui_modularity_findings(self._cfg(tool, products))
            self.assertTrue(findings)
            self.assertTrue(all(item["verdict"] == "PASS" for item in findings), findings)
            self.assertEqual(metrics["checked_products"], 1)

    def test_private_cross_product_ui_dependency_fails(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            tool = workspace / "LevelUpDiag-Koali"
            product = workspace / "orgo"
            tool.mkdir()
            product.mkdir()
            (product / "package.json").write_text('{"dependencies":{"@konnaxion/private-ui":"1"}}', encoding="utf-8")
            products = [{
                "id": "orgo",
                "root": "orgo",
                "scan_files": ["package.json"],
                "forbidden_private_ui_tokens": ["@konnaxion/private-ui"],
            }]
            findings, _ = collect_ui_modularity_findings(self._cfg(tool, products))
            failures = [item for item in findings if item["verdict"] == "FAIL"]
            self.assertEqual(len(failures), 1)
            self.assertIn("private_ui_dependency", failures[0]["id"])

    def test_product_relative_marker_cannot_escape_repository(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            tool = workspace / "LevelUpDiag-Koali"
            product = workspace / "orgo"
            tool.mkdir()
            product.mkdir()
            findings, _ = collect_ui_modularity_findings(
                self._cfg(tool, [{
                    "id": "orgo",
                    "root": "orgo",
                    "standalone_markers": ["../escape.tsx"],
                }])
            )
            self.assertEqual(findings[0]["verdict"], "CONFIG_ERROR")


if __name__ == "__main__":
    unittest.main()
