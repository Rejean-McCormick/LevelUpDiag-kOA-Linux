from pathlib import Path
import json
import unittest

from levelupdiag_core.manifest import load_manifest, resolve_selection

ROOT = Path(__file__).resolve().parents[1]


class StabilizationTests(unittest.TestCase):
    def test_stabilization_is_core_only(self):
        manifest = load_manifest(ROOT)
        selected = [x["id"] for x in resolve_selection(manifest, "stabilization")]
        self.assertEqual(selected, ["N00", "N01", "N04", "N05"])
        meta = manifest["campaigns"]["stabilization"]
        self.assertEqual(meta["mode"], "debug")
        self.assertEqual(meta["scope"], "koali_core_pre_subsystem")
        self.assertEqual(
            meta["deferred_subsystems"],
            ["konnaxion", "ariane", "orgo", "semantik_architect"],
        )

    def test_runtime_stabilization_excludes_integration_and_profile_levels(self):
        manifest = load_manifest(ROOT)
        selected = [x["id"] for x in resolve_selection(manifest, "stabilization-runtime")]
        self.assertEqual(selected, ["N00", "N01", "N04", "N05", "N08", "N09", "N10"])
        self.assertNotIn("N06", selected)
        self.assertNotIn("N07", selected)

    def test_environment_requires_native_core_build_toolchain(self):
        cfg = json.loads((ROOT / "levelupdiag.config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["default_campaign"], "stabilization")
        for tool in ("python", "uv", "git", "cargo", "rustc", "cc"):
            self.assertIn(tool, cfg["toolchain"]["required"])

    def test_legacy_control_panel_campaign_aliases_are_preserved(self):
        manifest = load_manifest(ROOT)
        self.assertEqual(
            [x["id"] for x in resolve_selection(manifest, "developer-fast")],
            ["N00", "N01", "N04", "N05"],
        )
        self.assertEqual(
            [x["id"] for x in resolve_selection(manifest, "nightly")],
            [f"N{i:02d}" for i in range(11)],
        )


    def test_cli_defaults_to_stabilization(self):
        from levelupdiag_core.cli import parser
        self.assertEqual(parser().parse_args(["run"]).selection, "stabilization")


if __name__ == "__main__":
    unittest.main()
