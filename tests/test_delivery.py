from pathlib import Path
import tempfile
import unittest
from levels.n11_delivery import _scan_dir

class DeliveryTests(unittest.TestCase):
    def test_detects_levelupdiag_residue(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app").mkdir()
            (root / "app" / "ok.txt").write_text("ok")
            (root / "levelupdiag").mkdir()
            matches = _scan_dir(root)
            self.assertTrue(any(rel == "levelupdiag" for rel, _ in matches))

if __name__ == "__main__": unittest.main()
