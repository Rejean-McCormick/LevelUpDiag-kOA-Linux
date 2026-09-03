from pathlib import Path
import sys
import tempfile
import unittest
from levelupdiag_core.commands import run_command

class CommandTests(unittest.TestCase):
    def test_shell_free_command_and_redaction(self):
        with tempfile.TemporaryDirectory() as td:
            r = run_command([sys.executable,"-c","print('password=verysecret')"], cwd=Path(td), timeout_seconds=10)
            self.assertEqual(r["exit_code"], 0)
            self.assertIn("<REDACTED>", r["stdout_tail"])
            self.assertNotIn("verysecret", r["stdout_tail"])

if __name__ == "__main__": unittest.main()
