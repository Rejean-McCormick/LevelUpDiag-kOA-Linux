"""N13: source checks and explicitly requested, read-only Linux session probes."""
from __future__ import annotations
import argparse
import ast
import configparser
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

EXPECTED_IDS = {
    'org.mozilla.firefox', 'org.videolan.VLC', 'org.mozilla.thunderbird',
    'io.github.peazip.PeaZip', 'com.github.dail8859.NotepadNext',
    'org.libreoffice.LibreOffice', 'org.keepassxc.KeePassXC',
}
LAUNCHERS = {'koali-store': 'store', 'koali-essentials': 'essentials'}
CAPABILITIES = {'third-party-flatpak', 'third-party-software-store', 'desktop-install-dialogs'}
MAPPINGS = {
    'host/store/third-party-store.py': '/usr/libexec/koa/third-party-store.py',
    **{'host/store/' + stem + '.desktop': '/usr/share/applications/' + stem + '.desktop' for stem in LAUNCHERS},
}


def probe(argv):
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=8, check=False)
        return {'returncode': p.returncode, 'stdout': p.stdout[-12000:], 'stderr': p.stderr[-2000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'returncode': -1, 'stdout': '', 'stderr': str(exc)}


def desktop_check(path, action, *, installed=False, source_script=None):
    p = configparser.ConfigParser(interpolation=None, strict=True)
    p.read_string(path.read_text(encoding='utf-8'))
    entry = p['Desktop Entry']
    argv = shlex.split(entry.get('Exec', ''))
    valid = (entry.get('Type') == 'Application' and entry.get('Terminal', '').lower() == 'false'
             and entry.get('Hidden', 'false').lower() != 'true' and bool(entry.get('Name'))
             and len(argv) == 3 and argv[0] == '/usr/bin/python3' and argv[2] == action)
    if valid:
        valid = (Path(argv[1]).is_file() and source_script is not None and Path(argv[1]).read_bytes() == source_script.read_bytes()) if installed else argv[1] == '/usr/libexec/koa/third-party-store.py'
    return valid


def collect_store_findings(cfg, *, platform_name=None, environ=None, which=shutil.which, run=probe):
    section = cfg.get('store', {})
    findings = []
    metrics = {'scope': 'store_sources', 'installation_performed': False, 'end_to_end_validated': False}
    def add(key, verdict, message, evidence=None):
        findings.append({'id': 'n13.' + key, 'verdict': verdict, 'category': 'runtime' if key.startswith('runtime.') else 'configuration', 'message': message, 'evidence': evidence})
    if not isinstance(section, dict) or not isinstance(section.get('runtime_checks', False), bool):
        add('config', 'CONFIG_ERROR', 'store must be an object with boolean runtime_checks.')
        return findings, metrics
    raw = Path(str(section.get('root', '../koa-linux'))).expanduser()
    root = raw if raw.is_absolute() else Path(cfg['_tool_root']) / raw
    def read(relative):
        return json.loads((root / relative).read_text(encoding='utf-8'))
    try:
        tree = ast.parse((root / 'host/store/third-party-store.py').read_text(encoding='utf-8'))
        constants = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {'CATALOG', 'REMOTE', 'REMOTE_FILE'}:
                        constants[target.id] = ast.literal_eval(node.value)
        catalog = constants.get('CATALOG', ())
        ids = [row[0] for row in catalog if isinstance(row, (tuple, list)) and len(row) == 3 and all(isinstance(v, str) and v for v in row)]
        valid = len(ids) == len(catalog) == len(EXPECTED_IDS) and set(ids) == EXPECTED_IDS
        add('catalog', 'PASS' if valid else 'FAIL', 'Essential application identifiers and labels.', {'ids': ids, 'expected': sorted(EXPECTED_IDS)})
        valid = constants.get('REMOTE') == 'koali-flathub' and constants.get('REMOTE_FILE') == 'https://flathub.org/repo/flathub.flatpakrepo'
        add('source_remote', 'PASS' if valid else 'FAIL', 'Installer uses the expected Flathub reference.')
    except (OSError, SyntaxError, ValueError, TypeError) as exc:
        add('catalog', 'FAIL', 'Store source is missing or invalid.', str(exc))
    for stem, action in LAUNCHERS.items():
        try:
            ok = desktop_check(root / 'host/store' / (stem + '.desktop'), action)
            add('launcher.' + stem, 'PASS' if ok else 'FAIL', 'Source launcher has the expected command.')
            admission = read('profiles/native-applications/admission/' + stem + '.json')
            ok = (admission.get('app_id') == stem and admission.get('enabled') is True
                  and admission.get('desktop_entry_refs') == [stem + '.desktop']
                  and admission.get('launch', {}).get('allowed_actions') == ['launch']
                  and admission.get('runtime', {}).get('allowed_profile_ids') == ['user_lightweight'])
            data_ref = admission.get('data_policy_ref')
            ok = ok and data_ref == 'data/' + stem + '.json'
            data = read('profiles/native-applications/data/' + stem + '.json')
            ok = ok and data.get('kind') == 'NativeApplicationDataPolicy' and bool(data.get('profile_locations'))
            add('admission.' + stem, 'PASS' if ok else 'FAIL', 'Launcher admission and data policy are present and consistent.')
        except (OSError, ValueError, KeyError, TypeError, AttributeError, configparser.Error) as exc:
            add('launcher.' + stem, 'FAIL', 'Launcher or policy is missing or invalid.', str(exc))
    try:
        caps = {item['id'] for item in read('host/image/package-sets/user-lightweight.yaml')['required_capabilities']}
        add('packages', 'PASS' if CAPABILITIES <= caps else 'FAIL', 'Image declares the store infrastructure.', {'missing': sorted(CAPABILITIES - caps)})
        mapping = read('.koa/runtime-paths.json')['repository_payload_mappings']
        ok = all(sum(row.get('source') == src and row.get('destination') == dst and row.get('install_mode') == 'copy' for row in mapping) == 1
                 and sum(row.get('destination') == dst for row in mapping) == 1 for src, dst in MAPPINGS.items())
        add('payload', 'PASS' if ok else 'FAIL', 'Store script and desktop launchers are projected uniquely into the image.')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        add('image', 'FAIL', 'Image package or payload declarations cannot be checked.', str(exc))
    add('source_tests', 'PASS' if (root / 'tests/system/test_third_party_store.py').is_file() else 'FAIL',
        'Installer test file presence only; N13 does not execute target repository code.')
    platform_name = platform_name or sys.platform
    env = dict(os.environ if environ is None else environ)
    metrics['host_platform'] = platform_name
    if not section.get('runtime_checks', False):
        add('runtime.coverage', 'PARTIAL', 'Linux session probes were not requested. Source checks do not validate the installed store.')
    elif platform_name != 'linux':
        add('runtime.platform', 'BLOCKED', 'Store runtime checks require execution inside the target Linux desktop session, not Windows.')
    else:
        metrics['scope'] = 'store_sources_and_linux_session'
        commands = ('flatpak', 'gnome-software', 'zenity', 'busctl')
        missing = [cmd for cmd in commands if not which(cmd)]
        add('runtime.tools', 'FAIL' if missing else 'PASS', 'Linux store tools are available.', {'missing': missing})
        graphical = bool(env.get('WAYLAND_DISPLAY') or env.get('DISPLAY')) and bool(env.get('XDG_RUNTIME_DIR')) and bool(env.get('DBUS_SESSION_BUS_ADDRESS'))
        add('runtime.session', 'PASS' if graphical else 'BLOCKED', 'A graphical session and user D-Bus environment are required.')
        # This is detection, not a claim that the plugin or portal works end to end.
        plugins = [str(p) for base in (Path('/usr/lib'), Path('/usr/lib64')) for pattern in ('gnome-software/plugins-*/*flatpak*.so', '*/gnome-software/plugins-*/*flatpak*.so') for p in base.glob(pattern)]
        add('runtime.plugin', 'PASS' if plugins else 'BLOCKED', 'GNOME Software Flatpak plugin files detected in standard system locations.', plugins)
        if graphical and which('busctl'):
            result = run(['busctl', '--user', '--timeout=5', 'status', 'org.freedesktop.portal.Desktop'])
            add('runtime.portal', 'PASS' if result['returncode'] == 0 else 'BLOCKED', 'Desktop portal owns its user-bus name; functional file-picker/audio checks remain separate.', result)
        else:
            add('runtime.portal', 'BLOCKED', 'Portal probe could not run without the session and busctl.')
        appdirs = [Path(env.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'applications']
        appdirs += [Path(p) / 'applications' for p in env.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]
        for stem, action in LAUNCHERS.items():
            # First entry wins, including invalid/hidden user overrides.
            entry = next((d / (stem + '.desktop') for d in appdirs if (d / (stem + '.desktop')).is_file()), None)
            try:
                ok = bool(entry) and desktop_check(entry, action, installed=True, source_script=root / "host/store/third-party-store.py")
            except (OSError, ValueError, KeyError, configparser.Error):
                ok = False
            add('runtime.launcher.' + stem, 'PASS' if ok else 'FAIL', 'Effective installed desktop shortcut and target script.', str(entry) if entry else None)
        if which('flatpak'):
            result = run(['flatpak', 'remotes', '--user', '--columns=name,url'])
            rows = [line.split() for line in result['stdout'].splitlines()]
            remote = next((row for row in rows if row and row[0] == 'koali-flathub'), None)
            verdict = 'BLOCKED' if result['returncode'] else ('WARN' if remote is None else ('PASS' if len(remote) == 2 and remote[1].rstrip('/') == 'https://dl.flathub.org/repo' else 'FAIL'))
            add('runtime.remote', verdict, 'User Flathub remote; absent means first-launch setup has not completed.', result)
            inventory = {}
            for scope in ('--user', '--system'):
                result = run(['flatpak', 'list', scope, '--app', '--columns=application'])
                inventory[scope] = result
            readable = all(item['returncode'] == 0 for item in inventory.values())
            present = set().union(*(set(item['stdout'].splitlines()) for item in inventory.values()))
            add('runtime.inventory', 'PASS' if readable else 'BLOCKED', 'Flatpak inventory only: essentials are optional; native equivalents are not counted.',
                {'present': sorted(EXPECTED_IDS & present), 'not_listed_as_flatpak': sorted(EXPECTED_IDS - present), 'queries': inventory})
    add('runtime.end_to_end', 'PARTIAL', 'No store window, download, install, uninstall or application launch performed. Run the documented VM acceptance scenario.')
    metrics['finding_count'] = len(findings)
    return findings, metrics


def run_store_diagnostics(cfg, report):
    findings, metrics = collect_store_findings(cfg)
    report.metrics['store'] = metrics
    for finding in findings:
        report.add(finding['id'], finding['verdict'], finding['category'], finding['message'], evidence=finding.get('evidence'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, help='kOA-Linux repository, not Koali Spaces')
    parser.add_argument('--runtime', action='store_true', help='Read-only probes in the current Linux desktop session')
    args = parser.parse_args(argv)
    findings, metrics = collect_store_findings({'_tool_root': str(Path.cwd()), 'store': {'root': args.root, 'runtime_checks': args.runtime}})
    print(json.dumps({'findings': findings, 'metrics': metrics}, indent=2, ensure_ascii=False))
    return 1 if any(f['verdict'] in {'FAIL', 'BLOCKED', 'CONFIG_ERROR', 'INFRA_ERROR', 'ERROR'} for f in findings) else 0


if __name__ == '__main__':
    raise SystemExit(main())
