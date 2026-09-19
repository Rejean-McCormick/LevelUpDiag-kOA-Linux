import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from levels.store_support import CAPABILITIES, EXPECTED_IDS, LAUNCHERS, MAPPINGS, collect_store_findings, desktop_check


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = {'_tool_root': str(self.root), 'store': {'root': str(self.root), 'runtime_checks': False}}
        self.write('host/store/third-party-store.py', 'raise RuntimeError("must never be imported")\nCATALOG = ' + repr(tuple((x, x, 'usage') for x in sorted(EXPECTED_IDS))) + '\nREMOTE = "koali-flathub"\nREMOTE_FILE = "https://flathub.org/repo/flathub.flatpakrepo"\n')
        self.write('tests/system/test_third_party_store.py', 'raise RuntimeError("must never run")')
        for stem, action in LAUNCHERS.items():
            self.write('host/store/' + stem + '.desktop', '[Desktop Entry]\nType=Application\nName=Test\nTerminal=false\nExec=/usr/bin/python3 /usr/libexec/koa/third-party-store.py ' + action + '\n')
            self.write_json('profiles/native-applications/admission/' + stem + '.json', {'app_id': stem, 'enabled': True, 'desktop_entry_refs': [stem + '.desktop'], 'runtime': {'allowed_profile_ids': ['user_lightweight']}, 'launch': {'allowed_actions': ['launch']}, 'data_policy_ref': 'data/' + stem + '.json'})
            self.write_json('profiles/native-applications/data/' + stem + '.json', {'kind': 'NativeApplicationDataPolicy', 'profile_locations': [{'root': 'xdg_state', 'relative_path': 'koali-store'}]})
        self.write_json('host/image/package-sets/user-lightweight.yaml', {'required_capabilities': [{'id': x} for x in CAPABILITIES]})
        self.write_json('.koa/runtime-paths.json', {'repository_payload_mappings': [{'source': src, 'destination': dst, 'install_mode': 'copy'} for src, dst in MAPPINGS.items()]})

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)

    def write_json(self, name, value):
        self.write(name, json.dumps(value))

    def findings(self, **kwargs):
        findings, metrics = collect_store_findings(self.cfg, **kwargs)
        return {f['id']: f for f in findings}, metrics

    def test_source_only_does_not_execute_any_process_or_target_code(self):
        def forbidden(*args):
            self.fail('process executed in source-only mode')
        findings, metrics = self.findings(run=forbidden)
        self.assertFalse(any(f['verdict'] == 'FAIL' for f in findings.values()))
        self.assertEqual(findings['n13.runtime.coverage']['verdict'], 'PARTIAL')
        self.assertFalse(metrics['end_to_end_validated'])

    def test_missing_catalog_fails(self):
        (self.root / 'host/store/third-party-store.py').unlink()
        findings, _ = self.findings()
        self.assertEqual(findings['n13.catalog']['verdict'], 'FAIL')

    def test_bad_desktop_command_fails(self):
        self.write('host/store/koali-store.desktop', '[Desktop Entry]\nName=Test\nType=Application\nTerminal=false\nExec=sh -c bad\n')
        findings, _ = self.findings()
        self.assertEqual(findings['n13.launcher.koali-store']['verdict'], 'FAIL')

    def test_duplicate_payload_destination_fails(self):
        path = self.root / '.koa/runtime-paths.json'
        data = json.loads(path.read_text())
        data['repository_payload_mappings'].append(data['repository_payload_mappings'][0])
        path.write_text(json.dumps(data))
        findings, _ = self.findings()
        self.assertEqual(findings['n13.payload']['verdict'], 'FAIL')

    def test_runtime_windows_is_blocked_not_pass(self):
        self.cfg['store']['runtime_checks'] = True
        findings, _ = self.findings(platform_name='win32')
        self.assertEqual(findings['n13.runtime.platform']['verdict'], 'BLOCKED')

    def test_headless_linux_and_missing_tools_are_explicit(self):
        self.cfg['store']['runtime_checks'] = True
        with patch.object(Path, 'glob', return_value=[]):
            findings, _ = self.findings(platform_name='linux', environ={}, which=lambda _: None)
        self.assertEqual(findings['n13.runtime.tools']['verdict'], 'FAIL')
        self.assertEqual(findings['n13.runtime.session']['verdict'], 'BLOCKED')
        self.assertEqual(findings['n13.runtime.plugin']['verdict'], 'BLOCKED')
        self.assertEqual(findings['n13.runtime.portal']['verdict'], 'BLOCKED')

    def test_runtime_is_read_only_and_rejects_wrong_remote(self):
        self.cfg['store']['runtime_checks'] = True
        commands = []
        def run(argv):
            commands.append(argv)
            return {'returncode': 0, 'stdout': 'koali-flathub\thttps://evil.example/repo\n' if argv[1] == 'remotes' else '', 'stderr': ''}
        with patch.object(Path, 'glob', return_value=[]):
            findings, metrics = self.findings(platform_name='linux', environ={'DISPLAY': ':1', 'XDG_RUNTIME_DIR': str(self.root), 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/test'}, which=lambda name: '/usr/bin/' + name, run=run)
        self.assertEqual(findings['n13.runtime.remote']['verdict'], 'FAIL')
        self.assertFalse(metrics['installation_performed'])
        self.assertTrue(all(cmd[1] in {'remotes', 'list', '--user'} for cmd in commands))
        self.assertFalse(any(token in {'install', 'remote-add', 'run', 'uninstall'} for cmd in commands for token in cmd))

    def test_malformed_image_json_fails_without_crashing(self):
        self.write('.koa/runtime-paths.json', '{')
        findings, _ = self.findings()
        self.assertEqual(findings['n13.image']['verdict'], 'FAIL')

    def test_runtime_flag_must_be_boolean(self):
        self.cfg['store']['runtime_checks'] = 'false'
        findings, _ = self.findings()
        self.assertEqual(findings['n13.config']['verdict'], 'CONFIG_ERROR')

    def test_installed_shortcut_must_match_source_script(self):
        source = self.root / 'host/store/third-party-store.py'
        installed = self.root / 'installed.py'
        installed.write_bytes(source.read_bytes())
        desktop = self.root / 'installed.desktop'
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Test\nTerminal=false\nExec=/usr/bin/python3 "' + str(installed) + '" store\n')
        self.assertTrue(desktop_check(desktop, 'store', installed=True, source_script=source))
        installed.write_text('unrelated code')
        self.assertFalse(desktop_check(desktop, 'store', installed=True, source_script=source))


if __name__ == '__main__':
    unittest.main()
