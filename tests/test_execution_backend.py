from pathlib import Path
import unittest

from levelupdiag_core.execution_backend import ExecutionBackendError, build_launch_plan


class _Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ExecutionBackendTests(unittest.TestCase):
    def test_native_backend_uses_supplied_python(self):
        cfg = {"desktop_console": {"execution_backend": "native"}}
        plan = build_launch_plan(
            Path("/opt/LevelUpDiag-Koali"), "audit-total", "debug", cfg,
            platform_name="posix", native_python="/usr/bin/python3",
        )
        self.assertEqual(plan.backend, "native")
        self.assertEqual(plan.command[0], "/usr/bin/python3")
        self.assertEqual(plan.command[-4:], ("run", "audit-total", "--mode", "debug"))

    def test_auto_on_windows_uses_wsl_with_augmented_user_path_without_shell(self):
        calls = []

        def fake_which(name):
            return r"C:\Windows\System32\wsl.exe" if name == "wsl.exe" else None

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            if "wslpath" in argv:
                return _Result(stdout="/mnt/c/mycode/kOA-Linux/LevelUpDiag-Koali/levelupdiag.py\n")
            if "-c" in argv:
                return _Result(stdout='{"home":"/home/rejean","path":"/usr/local/bin:/usr/bin:/bin"}\n')
            if "--version" in argv and "python3" in argv:
                return _Result(stdout="Python 3.13.7\n")
            return _Result(returncode=1, stderr="unexpected")

        cfg = {
            "desktop_console": {
                "execution_backend": "auto",
                "wsl_python_candidates": ["python3", "python"],
                "wsl_path_prepend": ["~/.local/bin", "~/.cargo/bin"],
            }
        }
        plan = build_launch_plan(
            Path(r"C:\mycode\kOA-Linux\LevelUpDiag-Koali"), "audit-total", "debug", cfg,
            platform_name="nt", native_python=r"C:\Python\python.exe", which=fake_which, run=fake_run,
        )
        self.assertEqual(plan.backend, "wsl")
        self.assertEqual(plan.runtime, "python3 + user PATH")
        self.assertEqual(plan.command[0], r"C:\Windows\System32\wsl.exe")
        self.assertEqual(plan.command[1:3], ("--exec", "/usr/bin/env"))
        self.assertEqual(
            plan.command[3],
            "PATH=/home/rejean/.local/bin:/home/rejean/.cargo/bin:/usr/local/bin:/usr/bin:/bin",
        )
        self.assertEqual(plan.command[4:6], ("python3", "/mnt/c/mycode/kOA-Linux/LevelUpDiag-Koali/levelupdiag.py"))
        self.assertEqual(plan.command[-4:], ("run", "audit-total", "--mode", "debug"))
        self.assertTrue(all(kwargs.get("shell") is False for _, kwargs in calls))

    def test_wsl_path_prepend_deduplicates_existing_entries(self):
        def fake_which(name):
            return "wsl.exe" if name == "wsl.exe" else None

        def fake_run(argv, **kwargs):
            if "wslpath" in argv:
                return _Result(stdout="/mnt/c/tool/levelupdiag.py\n")
            if "-c" in argv:
                return _Result(stdout='{"home":"/home/u","path":"/home/u/.local/bin:/usr/bin"}\n')
            if "--version" in argv:
                return _Result(stdout="Python 3.13\n")
            return _Result(returncode=1)

        cfg = {"desktop_console": {"execution_backend": "wsl", "wsl_path_prepend": ["~/.local/bin", "~/.cargo/bin"]}}
        plan = build_launch_plan(Path(r"C:\tool"), "debug", "debug", cfg, platform_name="nt", which=fake_which, run=fake_run)
        path_value = plan.command[3]
        self.assertEqual(path_value.count("/home/u/.local/bin"), 1)
        self.assertIn("/home/u/.cargo/bin", path_value)

    def test_invalid_wsl_path_prepend_is_rejected(self):
        def fake_which(name):
            return "wsl.exe" if name == "wsl.exe" else None

        def fake_run(argv, **kwargs):
            if "wslpath" in argv:
                return _Result(stdout="/mnt/c/tool/levelupdiag.py\n")
            if "--version" in argv:
                return _Result(stdout="Python 3.13\n")
            return _Result(returncode=1)

        cfg = {"desktop_console": {"execution_backend": "wsl", "wsl_path_prepend": "~/.local/bin"}}
        with self.assertRaisesRegex(ExecutionBackendError, "wsl_path_prepend must be a list"):
            build_launch_plan(Path(r"C:\tool"), "debug", "debug", cfg, platform_name="nt", which=fake_which, run=fake_run)

    def test_auto_on_windows_does_not_silently_fall_back_to_native(self):
        cfg = {"desktop_console": {"execution_backend": "auto"}}
        with self.assertRaisesRegex(ExecutionBackendError, "WSL is required"):
            build_launch_plan(
                Path(r"C:\mycode\kOA-Linux\LevelUpDiag-Koali"), "debug", "debug", cfg,
                platform_name="nt", native_python=r"C:\Python\python.exe", which=lambda _name: None,
            )

    def test_invalid_backend_is_rejected(self):
        cfg = {"desktop_console": {"execution_backend": "magic"}}
        with self.assertRaisesRegex(ExecutionBackendError, "auto, native, wsl"):
            build_launch_plan(Path("/tmp/tool"), "debug", "debug", cfg, platform_name="posix")


if __name__ == "__main__":
    unittest.main()
