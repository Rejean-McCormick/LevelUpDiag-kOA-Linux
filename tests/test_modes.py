import unittest

from levelupdiag_core.modes import normalize_mode, policy_for
from levelupdiag_core.verdicts import (
    campaign_verdict,
    execution_verdict,
    testability as compute_testability,
)


class ModeTests(unittest.TestCase):
    def test_debug_has_no_dependency_blockers_and_no_git_protection(self):
        policy = policy_for({}, "debug")
        self.assertEqual(policy["dependency_blocking_verdicts"], set())
        self.assertFalse(policy["protect_tracked_files"])

    def test_release_is_strict(self):
        policy = policy_for({}, "release")
        self.assertIn("BLOCKED", policy["dependency_blocking_verdicts"])
        self.assertIn("CONFIG_ERROR", policy["dependency_blocking_verdicts"])
        self.assertTrue(policy["protect_tracked_files"])

    def test_debug_campaign_demotes_target_blockage_to_warn(self):
        levels = [
            {"level_id":"N00", "verdict":"PASS"},
            {"level_id":"N08", "verdict":"BLOCKED"},
            {"level_id":"N10", "verdict":"FAIL"},
            {"level_id":"N02", "verdict":"CONFIG_ERROR"},
        ]
        required = {"N00":True, "N08":False, "N10":False, "N02":False}
        self.assertEqual(campaign_verdict(levels, required, "debug"), "WARN")
        self.assertEqual(execution_verdict(levels), "PASS")
        self.assertEqual(compute_testability(levels), "PARTIAL")

    def test_debug_execution_error_remains_error(self):
        levels = [{"level_id":"N00", "verdict":"INFRA_ERROR"}]
        self.assertEqual(campaign_verdict(levels, {"N00":True}, "debug"), "ERROR")
        self.assertEqual(execution_verdict(levels), "ERROR")

    def test_mode_validation(self):
        self.assertEqual(normalize_mode("DEBUG"), "debug")
        with self.assertRaises(ValueError):
            normalize_mode("anything")


if __name__ == "__main__": unittest.main()
