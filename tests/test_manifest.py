from pathlib import Path
import tomllib
import unittest

from levelupdiag_core.manifest import load_manifest, resolve_selection

ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def test_sequence_is_stable_and_serial(self):
        m = load_manifest(ROOT)
        levels = sorted(m["levels"], key=lambda x:(x.get("order",0),x["id"]))
        self.assertEqual([x["id"] for x in levels], [f"N{i:02d}" for i in range(12)])
        self.assertTrue(all(x.get("parallel_safe") is False for x in levels))

    def test_debug_excludes_formalities(self):
        m = load_manifest(ROOT)
        selected = [x["id"] for x in resolve_selection(m, "debug")]
        self.assertEqual(selected, ["N00","N01","N04","N05","N06","N07","N08","N09","N10"])
        self.assertNotIn("N02", selected)
        self.assertNotIn("N03", selected)
        self.assertNotIn("N11", selected)

    def test_audit_total_preserves_n00_to_n10_non_blocking_scope(self):
        m = load_manifest(ROOT)
        self.assertEqual([x["id"] for x in resolve_selection(m, "audit-total")], [f"N{i:02d}" for i in range(11)])
        self.assertEqual(m["campaigns"]["audit-total"]["mode"], "debug")
        self.assertEqual(m["campaigns"]["audit-total"]["scope"], "full_target_diagnostic")

    def test_suite_version_matches_package_version(self):
        m = load_manifest(ROOT)
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(m["suite_version"], project["project"]["version"])

    def test_validation_preserves_n00_to_n10(self):
        m = load_manifest(ROOT)
        self.assertEqual([x["id"] for x in resolve_selection(m, "validation")], [f"N{i:02d}" for i in range(11)])

    def test_functional_selection_no_longer_adds_repository_formality(self):
        m = load_manifest(ROOT)
        selected = [x["id"] for x in resolve_selection(m, "N08,N09,N10")]
        self.assertEqual(selected, ["N00","N01","N04","N05","N08","N09","N10"])

    def test_required_functional_levels(self):
        m = load_manifest(ROOT)
        required = [x["id"] for x in m["levels"] if x.get("required")]
        self.assertEqual(required, ["N00","N01","N04","N05"])

    def test_multi_level_selection_rejects_unknown_level(self):
        m = load_manifest(ROOT)
        with self.assertRaisesRegex(Exception, "Unknown level"):
            resolve_selection(m, "N02,N99")


if __name__ == "__main__": unittest.main()
