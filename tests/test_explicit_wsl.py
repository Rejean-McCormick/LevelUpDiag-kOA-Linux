import json
from pathlib import Path
import subprocess
import unittest
from levelupdiag_core.execution_backend import build_launch_plan, ExecutionBackendError

class ExplicitWSLTests(unittest.TestCase):
    def test_every_probe_and_launch_uses_same_distro_and_linux_target(self):
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(argv[:4], ['wsl.exe', '-d', 'Ubuntu-24.04', '--exec'])
            self.assertEqual(kwargs['timeout'], 30)
            output = '/mnt/c/tool/levelupdiag.py' if 'wslpath' in argv else json.dumps({'home':'/home/rejean','path':'/usr/bin'}) if '-c' in argv else 'Python 3.13'
            return subprocess.CompletedProcess(argv, 0, output, '')
        cfg = {'desktop_console': {'wsl_distro':'Ubuntu-24.04','wsl_target_root':'~/work/koa-linux'}}
        plan = build_launch_plan(Path('C:/tool'), 'audit-total', 'debug', cfg, platform_name='nt', which=lambda _: 'wsl.exe', run=run)
        self.assertEqual(len(calls), 3)
        self.assertEqual(plan.command[:4], ('wsl.exe','-d','Ubuntu-24.04','--exec'))
        self.assertEqual(plan.command[-6:], ('--target','/home/rejean/work/koa-linux','run','audit-total','--mode','debug'))
        self.assertIn('Ubuntu-24.04', plan.label)

    def test_windows_shell_does_not_probe_wsl(self):
        cfg = json.loads((Path(__file__).resolve().parents[1]/'levelupdiag.config.json').read_text())
        def forbidden(*args, **kwargs):
            self.fail('Windows Shell must remain native')
        plan = build_launch_plan(Path('C:/tool'), 'koali-system','validation',cfg,platform_name='nt',native_python='python.exe',which=forbidden,run=forbidden)
        self.assertEqual(plan.backend, 'native')
