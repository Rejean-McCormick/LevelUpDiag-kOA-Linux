from pathlib import Path
import unittest
from levelupdiag_core.manifest import load_manifest, resolve_selection

ROOT = Path(__file__).resolve().parents[1]

class ManifestTests(unittest.TestCase):
    def test_sequence_is_stable_and_serial(self):
        m = load_manifest(ROOT)
        levels = sorted(m["levels"], key=lambda x:(x.get("order",0),x["id"]))
        self.assertEqual([x["id"] for x in levels], [f"N{i:02d}" for i in range(12)])
        self.assertTrue(all(x.get("parallel_safe") is False for x in levels))

    def test_standard_excludes_delivery(self):
        m = load_manifest(ROOT)
        self.assertEqual([x["id"] for x in resolve_selection(m, "standard")], [f"N{i:02d}" for i in range(11)])

    def test_required_koali_levels_preserved(self):
        m = load_manifest(ROOT)
        required = [x["id"] for x in m["levels"] if x.get("required")]
        self.assertEqual(required, ["N00","N01","N02","N03","N04","N05"])

if __name__ == "__main__": unittest.main()
