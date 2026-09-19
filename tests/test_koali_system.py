from __future__ import annotations

import json
import urllib.error
import urllib.request
import tempfile
from unittest.mock import patch
import unittest
from datetime import datetime, timezone
from pathlib import Path

from levels.koali_system_support import _public_shell_privacy_findings, evaluate_loaded_state, collect_koali_system_findings, _LoopbackRedirectHandler, http_get


class KoaliSystemTests(unittest.TestCase):
    def _fixture(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        tool = root / "LevelUpDiag-Koali"
        koali = root / "koali-spaces"
        tool.mkdir()
        koali.mkdir()
        products = [
            ("konnaxion", "konnaxion", True, False),
            ("orgo", "orgo", True, False),
            ("semantik_architect", "semantik_architect", False, True),
            ("koa_mediatheque", "koa_mediatheque", True, False),
        ]
        expected = []
        discovery = []
        runtimes = {}
        registrations = []
        targets = []
        modules = [{"module_id": "space_home"}]
        health = []
        for product_id, module_id, critical, allow_unready in products:
            expected.append({
                "id": product_id,
                "module_id": module_id,
                "shell_critical": critical,
                "allow_unready": allow_unready,
            })
            contract = root / f"{product_id}.integration.json"
            contract.write_text("{}", encoding="utf-8")
            discovery.append({
                "id": product_id,
                "moduleId": module_id,
                "repoFound": True,
                "externallyManaged": False,
                "integrationReady": True,
                "integrationFile": str(contract),
            })
            runtime_state = "degraded" if allow_unready else "ready"
            runtimes[product_id] = {"state": runtime_state, "reason": "accepted test outage" if allow_unready else "ready", "probes": []}
            registrations.append({"moduleId": module_id})
            targets.append({"moduleId": module_id, "embedBase": f"http://127.0.0.1:{4300 + len(targets) + 1}"})
            modules.append({
                "module_id": module_id,
                "routes": [{"route_id": f"{module_id}.home"}],
                "sidebar": {"items": []},
                "ui_portability": {"integrated_supported": True, "standalone_supported": True},
                "authority_boundary": {
                    "presentation_only": True,
                    "may_grant_capabilities": False,
                    "direct_domain_writes": False,
                },
            })
            health.append({
                "module_id": module_id,
                "state": runtime_state,
                "affects_shell_state": critical,
            })
        cfg = {
            "_tool_root": str(tool),
            "koali_system": {
                "root": str(koali),
                "max_state_age_seconds": 30,
                "expected_network_state": "online",
                "expected_products": expected,
            },
        }
        ecosystem = {
            "updatedAt": "2026-09-18T22:00:00Z",
            "discovery": {"products": discovery},
            "runtimes": runtimes,
        }
        surface = {"runtimeRegistrations": registrations, "resolvedTargets": targets}
        active = {
            "state": "ready",
            "network_state": "online",
            "reason": None,
            "modules": modules,
            "module_health": health,
            "capabilities": [],
        }
        return tmp, cfg, koali, ecosystem, surface, active

    def test_optional_semantik_outage_does_not_fail_koali_system(self):
        tmp, cfg, koali, ecosystem, surface, active = self._fixture()
        self.addCleanup(tmp.cleanup)
        findings, _ = evaluate_loaded_state(
            cfg,
            koali_root=koali,
            ecosystem=ecosystem,
            surface=surface,
            active=active,
            now=datetime(2026, 9, 18, 22, 0, 5, tzinfo=timezone.utc),
        )
        bad = [f for f in findings if f["verdict"] in {"FAIL", "BLOCKED", "CONFIG_ERROR", "INFRA_ERROR", "ERROR"}]
        self.assertEqual(bad, [])
        semantik = next(f for f in findings if f["id"] == "n12.product.semantik_architect.runtime")
        self.assertEqual(semantik["verdict"], "WARN")
        self.assertIn("explicitly accepted", semantik["message"])

    def test_required_product_outage_fails_system(self):
        tmp, cfg, koali, ecosystem, surface, active = self._fixture()
        self.addCleanup(tmp.cleanup)
        ecosystem["runtimes"]["orgo"] = {"state": "degraded", "reason": "api unreachable", "probes": []}
        for item in active["module_health"]:
            if item["module_id"] == "orgo":
                item["state"] = "degraded"
        active["state"] = "degraded"
        active["reason"] = "Development ecosystem degraded — Orgo"
        findings, _ = evaluate_loaded_state(
            cfg,
            koali_root=koali,
            ecosystem=ecosystem,
            surface=surface,
            active=active,
            now=datetime(2026, 9, 18, 22, 0, 5, tzinfo=timezone.utc),
        )
        orgo = next(f for f in findings if f["id"] == "n12.product.orgo.runtime")
        shell = next(f for f in findings if f["id"] == "n12.shell.canonical_state")
        self.assertEqual(orgo["verdict"], "FAIL")
        self.assertEqual(shell["verdict"], "FAIL")

    def test_public_shell_state_rejects_orchestration_private_fields(self):
        findings = _public_shell_privacy_findings({
            "state": "ready",
            "modules": [],
            "repoPath": r"C:\\mycode\\Orgo\\Orgo",
        })
        self.assertEqual(findings[0]["verdict"], "FAIL")
        self.assertIn("$.repoPath", findings[0]["evidence"]["exposed_paths"])

    def prepare_state(self, live_http):
        tmp, cfg, koali, ecosystem, surface, active = self._fixture()
        self.addCleanup(tmp.cleanup)
        cfg['koali_system']['live_http'] = live_http
        state = koali / '.koali-dev/state'
        state.mkdir(parents=True)
        for name, value in [('ecosystem-status', ecosystem), ('surface-runtime', surface), ('active-state', active)]:
            (state / (name + '.json')).write_text(json.dumps(value))
        for name in ('RUN_KOALI.cmd', 'KOALI.pyw'):
            (koali / name).touch()
        return cfg, active

    def test_disabled_http_is_explicit_partial(self):
        cfg, _ = self.prepare_state(False)
        findings, metrics = collect_koali_system_findings(cfg, http_client=lambda *_: self.fail('HTTP must not run'))
        result = next(f for f in findings if f['id'] == 'n12.live_http.coverage')
        self.assertEqual(result['verdict'], 'PARTIAL')
        self.assertFalse(metrics['live_http_checked'])

    def test_missing_product_probes_are_partial(self):
        cfg, active = self.prepare_state(True)
        findings, _ = collect_koali_system_findings(cfg, http_client=lambda *_: {'ok': True, 'body': json.dumps(active)})
        probes = [f for f in findings if f['id'].endswith('.live_probes')]
        self.assertEqual(len(probes), 4)
        self.assertTrue(all(f['verdict'] == 'PARTIAL' for f in probes))

    def test_non_loopback_redirect_is_refused(self):
        handler = _LoopbackRedirectHandler()
        request = urllib.request.Request('http://127.0.0.1:4173/')
        with self.assertRaises(urllib.error.URLError):
            handler.redirect_request(request, None, 302, 'Found', {}, 'https://example.org/')

    def test_local_redirect_is_allowed(self):
        request = urllib.request.Request('http://127.0.0.1:4173/')
        redirected = _LoopbackRedirectHandler().redirect_request(request, None, 302, 'Found', {}, '/next')
        self.assertEqual(redirected.full_url, 'http://127.0.0.1:4173/next')

    def test_http_uses_no_environment_proxy_and_guarded_redirects(self):
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.side_effect = urllib.error.URLError('test')
            self.assertFalse(http_get('http://127.0.0.1/', 1)['ok'])
            proxy, redirect = build.call_args.args
            self.assertEqual(proxy.proxies, {})
            self.assertIsInstance(redirect, _LoopbackRedirectHandler)


if __name__ == "__main__":
    unittest.main()
