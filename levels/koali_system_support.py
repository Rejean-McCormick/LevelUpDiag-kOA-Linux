from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_WINDOWS_ABS_RE = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")


def _finding(
    finding_id: str,
    verdict: str,
    category: str,
    message: str,
    *,
    evidence: Any = None,
    recommendation: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": finding_id,
        "verdict": verdict,
        "category": category,
        "message": message,
    }
    if evidence is not None:
        item["evidence"] = evidence
    if recommendation is not None:
        item["recommendation"] = recommendation
    if path is not None:
        item["path"] = path
    return item


def _section(cfg: dict) -> dict:
    value = cfg.get("koali_system", {})
    return value if isinstance(value, dict) else {}


def resolve_koali_root(cfg: dict) -> Path:
    section = _section(cfg)
    raw = Path(str(section.get("root", "../koali-spaces"))).expanduser()
    if raw.is_absolute():
        return raw.resolve(strict=False)
    return (Path(cfg["_tool_root"]) / raw).resolve(strict=False)


def resolve_state_root(cfg: dict, koali_root: Path) -> Path:
    raw = Path(str(_section(cfg).get("state_dir", ".koali-dev/state")))
    return raw.resolve(strict=False) if raw.is_absolute() else (koali_root / raw).resolve(strict=False)


def host_path(raw: str | Path) -> Path:
    """Resolve a host path from native Windows or WSL without invoking a shell."""
    text = str(raw)
    candidate = Path(text)
    if candidate.exists() or os.name == "nt":
        return candidate
    match = _WINDOWS_ABS_RE.match(text)
    if match:
        rest = match.group("rest").replace("\\", "/")
        return Path("/mnt") / match.group("drive").lower() / rest
    return candidate


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _loopback_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").casefold() in _LOOPBACK_HOSTS


class _LoopbackRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        if not _loopback_url(target):
            raise urllib.error.URLError("non-loopback redirect refused")
        return super().redirect_request(req, fp, code, msg, headers, target)


def http_get(url: str, timeout: float) -> dict[str, Any]:
    """GET a loopback URL only. LevelUpDiag never turns this into general network access."""
    if not _loopback_url(url):
        return {"url": url, "status": None, "ok": False, "error": "non-loopback URL refused"}
    request = urllib.request.Request(url, headers={"User-Agent": "LevelUpDiag-Koali/2.6"})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), _LoopbackRedirectHandler()).open(request, timeout=timeout) as response:  # noqa: S310 - loopback guarded above
            body = response.read(1024 * 1024)
            return {
                "url": url,
                "status": int(response.status),
                "ok": 200 <= int(response.status) < 300,
                "content_type": response.headers.get("Content-Type", ""),
                "body": body.decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(256 * 1024).decode("utf-8", errors="replace")
        return {"url": url, "status": int(exc.code), "ok": False, "body": body, "error": str(exc)}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"url": url, "status": None, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _expected_products(section: dict) -> list[dict]:
    products = section.get("expected_products", [])
    if not isinstance(products, list):
        return []
    return [item for item in products if isinstance(item, dict) and item.get("id")]


def _product_policy(item: dict) -> tuple[str, str, bool, bool, bool]:
    product_id = str(item.get("id"))
    module_id = str(item.get("module_id") or product_id)
    shell_critical = bool(item.get("shell_critical", True))
    allow_unready = bool(item.get("allow_unready", False))
    presentation = bool(item.get("presentation", True))
    return product_id, module_id, shell_critical, allow_unready, presentation


def _expected_sources(section: dict) -> list[dict]:
    values = section.get("expected_sources", [])
    if not isinstance(values, list):
        return []
    result: list[dict] = []
    for value in values:
        if isinstance(value, str) and value:
            result.append({"id": value, "required": True})
        elif isinstance(value, dict) and value.get("id"):
            result.append(dict(value))
    return result


def _by(items: Any, key: str) -> dict[str, dict]:
    if not isinstance(items, list):
        return {}
    result: dict[str, dict] = {}
    for item in items:
        if isinstance(item, dict) and item.get(key) is not None:
            result[str(item[key])] = item
    return result


def _module_ids(state: dict) -> list[str]:
    modules = state.get("modules", [])
    if not isinstance(modules, list):
        return []
    return [str(item.get("module_id")) for item in modules if isinstance(item, dict) and item.get("module_id")]


def _walk_keys(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}"
            found.append((next_path, str(key)))
            found.extend(_walk_keys(item, next_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_keys(item, f"{path}[{index}]"))
    return found


def evaluate_loaded_state(
    cfg: dict,
    *,
    koali_root: Path,
    ecosystem: dict,
    surface: dict,
    active: dict,
    now: datetime | None = None,
) -> tuple[list[dict], dict]:
    """Evaluate the canonical KS4 ecosystem state without performing HTTP requests."""
    section = _section(cfg)
    expected = _expected_products(section)
    findings: list[dict] = []
    metrics: dict[str, Any] = {"expected_products": len(expected)}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    updated = _iso_datetime(ecosystem.get("updatedAt"))
    max_age = float(section.get("max_state_age_seconds", 30))
    if updated is None:
        findings.append(_finding(
            "n12.state.freshness", "FAIL", "runtime",
            "ecosystem-status.json does not expose a parseable updatedAt timestamp.",
        ))
    else:
        age = max(0.0, (now - updated).total_seconds())
        metrics["state_age_seconds"] = round(age, 3)
        findings.append(_finding(
            "n12.state.freshness",
            "PASS" if age <= max_age else "FAIL",
            "runtime",
            "Koali ecosystem state is fresh." if age <= max_age else "Koali ecosystem state is stale.",
            evidence={"updatedAt": ecosystem.get("updatedAt"), "age_seconds": round(age, 3), "max_age_seconds": max_age},
            recommendation=None if age <= max_age else "Start/restart Koali with RUN_KOALI.cmd and rerun the live system diagnostic.",
        ))

    discovery = ecosystem.get("discovery", {}) if isinstance(ecosystem.get("discovery"), dict) else {}
    discovered = _by(discovery.get("products", []), "id")
    runtimes = ecosystem.get("runtimes", {}) if isinstance(ecosystem.get("runtimes"), dict) else {}
    registrations = _by(surface.get("runtimeRegistrations", []), "moduleId")
    targets = _by(surface.get("resolvedTargets", []), "moduleId")
    health = _by(active.get("module_health", []), "module_id")
    modules = _by(active.get("modules", []), "module_id")

    metrics["discovered_products"] = sorted(discovered)
    metrics["projected_modules"] = _module_ids(active)

    for item in expected:
        product_id, module_id, shell_critical, allow_unready, presentation = _product_policy(item)
        product = discovered.get(product_id)
        if product is None:
            findings.append(_finding(
                f"n12.product.{product_id}.discovery", "FAIL", "integration",
                f"Expected Koali product '{product_id}' is not present in ecosystem discovery.",
                recommendation="Repair workspace discovery or the ecosystem catalog; do not copy the product into Koali.",
            ))
            continue

        integration_ready = product.get("integrationReady") is True
        repo_ready = product.get("repoFound") is True or product.get("externallyManaged") is True
        findings.append(_finding(
            f"n12.product.{product_id}.contract",
            "PASS" if integration_ready and repo_ready else "FAIL",
            "integration",
            f"Owner contract for '{product_id}' is linked and discoverable."
            if integration_ready and repo_ready
            else f"Owner contract for '{product_id}' is not fully linked.",
            evidence={
                "repoFound": product.get("repoFound"),
                "externallyManaged": product.get("externallyManaged"),
                "integrationReady": product.get("integrationReady"),
                "integrationFile": product.get("integrationFile"),
            },
        ))

        integration_file = product.get("integrationFile")
        if integration_file:
            integration_path = host_path(str(integration_file))
            findings.append(_finding(
                f"n12.product.{product_id}.contract_file",
                "PASS" if integration_path.is_file() else "FAIL",
                "integration",
                f"Owner contract file for '{product_id}' exists."
                if integration_path.is_file()
                else f"Owner contract file for '{product_id}' is missing.",
                path=str(integration_path),
            ))

        runtime = runtimes.get(product_id) if isinstance(runtimes.get(product_id), dict) else {}
        runtime_state = str(runtime.get("state") or "unknown")
        accepted = runtime_state == "ready" or allow_unready
        if runtime_state == "ready":
            runtime_message = f"Runtime '{product_id}' is ready."
        elif allow_unready:
            runtime_message = f"Runtime '{product_id}' is {runtime_state}; this optional outage is explicitly accepted."
        else:
            runtime_message = f"Runtime '{product_id}' is not ready ({runtime_state})."
        findings.append(_finding(
            f"n12.product.{product_id}.runtime",
            "PASS" if runtime_state == "ready" else ("WARN" if allow_unready else "FAIL"),
            "runtime",
            runtime_message,
            evidence={"state": runtime_state, "reason": runtime.get("reason"), "allow_unready": allow_unready},
            recommendation=None if accepted else "Inspect the owner runtime probes and process state in ecosystem-status.json.",
        ))

        if presentation:
            registration_ok = module_id in registrations
            target = targets.get(module_id)
            target_ok = isinstance(target, dict) and isinstance(target.get("embedBase"), str) and _loopback_url(str(target.get("embedBase")))
            findings.append(_finding(
                f"n12.product.{product_id}.surface",
                "PASS" if registration_ok and target_ok else "FAIL",
                "presentation",
                f"Koali surface registration for '{product_id}' is coherent."
                if registration_ok and target_ok
                else f"Koali surface registration for '{product_id}' is incomplete.",
                evidence={"runtime_registration": registration_ok, "resolved_target": target},
            ))

            manifest = modules.get(module_id)
            if not isinstance(manifest, dict):
                findings.append(_finding(
                    f"n12.product.{product_id}.projection", "FAIL", "presentation",
                    f"Module '{module_id}' is missing from active-state.json.",
                ))
            else:
                routes = manifest.get("routes", [])
                sidebar_items = (manifest.get("sidebar") or {}).get("items", []) if isinstance(manifest.get("sidebar"), dict) else None
                portability = manifest.get("ui_portability", {}) if isinstance(manifest.get("ui_portability"), dict) else {}
                boundary = manifest.get("authority_boundary", {}) if isinstance(manifest.get("authority_boundary"), dict) else {}
                projection_ok = (
                    isinstance(routes, list) and len(routes) >= 1
                    and sidebar_items == []
                    and portability.get("integrated_supported") is True
                    and portability.get("standalone_supported") is True
                    and boundary.get("presentation_only") is True
                    and boundary.get("may_grant_capabilities") is False
                    and boundary.get("direct_domain_writes") is False
                )
                findings.append(_finding(
                    f"n12.product.{product_id}.projection",
                    "PASS" if projection_ok else "FAIL",
                    "presentation",
                    f"Module '{module_id}' preserves the owner-UI boundary."
                    if projection_ok
                    else f"Module '{module_id}' does not match the expected owner-UI projection boundary.",
                    evidence={
                        "routes": len(routes) if isinstance(routes, list) else None,
                        "sidebar_items": sidebar_items,
                        "ui_portability": portability,
                        "authority_boundary": boundary,
                    },
                ))

            item_health = health.get(module_id)
            if not isinstance(item_health, dict):
                findings.append(_finding(
                    f"n12.product.{product_id}.module_health", "FAIL", "presentation",
                    f"Module health for '{module_id}' is not projected.",
                ))
            else:
                affects = item_health.get("affects_shell_state") is True
                semantics_ok = affects == shell_critical
                health_state = str(item_health.get("state") or "unknown")
                ready_ok = health_state == "ready" or allow_unready
                findings.append(_finding(
                    f"n12.product.{product_id}.module_health",
                    "PASS" if semantics_ok and ready_ok else "FAIL",
                    "presentation",
                    f"Module health semantics for '{module_id}' are correct."
                    if semantics_ok and ready_ok
                    else f"Module health semantics for '{module_id}' are inconsistent.",
                    evidence={
                        "state": health_state,
                        "affects_shell_state": item_health.get("affects_shell_state"),
                        "expected_shell_critical": shell_critical,
                        "allow_unready": allow_unready,
                    },
                ))
        else:
            absent_from_surface = module_id not in registrations and module_id not in targets
            findings.append(_finding(
                f"n12.product.{product_id}.headless_surface",
                "PASS" if absent_from_surface else "FAIL",
                "presentation",
                f"Headless product '{product_id}' is correctly absent from the Koali iframe/surface registry."
                if absent_from_surface else f"Headless product '{product_id}' was incorrectly projected as a Koali web surface.",
                evidence={"runtime_registration_present": module_id in registrations, "resolved_target_present": module_id in targets},
            ))
            absent_from_projection = module_id not in modules and module_id not in health
            findings.append(_finding(
                f"n12.product.{product_id}.headless_projection",
                "PASS" if absent_from_projection else "FAIL",
                "presentation",
                f"Headless product '{product_id}' remains a capability/runtime and is not exposed as a fake module UI."
                if absent_from_projection else f"Headless product '{product_id}' is incorrectly present in the active UI projection.",
                evidence={"module_present": module_id in modules, "module_health_present": module_id in health},
            ))

    required_modules = {"space_home", *[str(item.get("module_id") or item["id"]) for item in expected if bool(item.get("presentation", True))]}
    projected = set(_module_ids(active))
    missing_modules = sorted(required_modules - projected)
    findings.append(_finding(
        "n12.shell.modules",
        "PASS" if not missing_modules else "FAIL",
        "presentation",
        "All expected Koali modules are projected into the active Space."
        if not missing_modules
        else "One or more expected Koali modules are missing from the active Space.",
        evidence={"projected": sorted(projected), "missing": missing_modules},
    ))

    expected_network = str(section.get("expected_network_state", "online"))
    shell_ready = active.get("state") == "ready"
    network_ok = active.get("network_state") == expected_network
    reason_ok = active.get("reason") in (None, "") if shell_ready else True
    findings.append(_finding(
        "n12.shell.canonical_state",
        "PASS" if shell_ready and network_ok and reason_ok else "FAIL",
        "runtime",
        "Canonical Koali shell state is ready and online."
        if shell_ready and network_ok and reason_ok
        else "Canonical Koali shell state is not in the expected ready/online condition.",
        evidence={
            "state": active.get("state"),
            "network_state": active.get("network_state"),
            "reason": active.get("reason"),
            "expected_network_state": expected_network,
        },
        recommendation=None if shell_ready and network_ok and reason_ok else "Inspect shell-critical presentation-product health and required runtime readiness in ecosystem-status.json.",
    ))

    return findings, metrics


def _public_shell_privacy_findings(value: dict) -> list[dict]:
    forbidden_keys = {"repoPath", "repo_path", "integrationFile", "integration_file", "commands", "cwd", "pids"}
    exposed = [path for path, key in _walk_keys(value) if key.startswith("_") or key in forbidden_keys]
    return [_finding(
        "n12.shell.public_boundary",
        "PASS" if not exposed else "FAIL",
        "security",
        "Public shell state does not expose orchestration-private fields."
        if not exposed
        else "Public shell state exposes orchestration-private fields.",
        evidence={"exposed_paths": exposed[:50]},
    )]


def collect_koali_system_findings(
    cfg: dict,
    *,
    now: datetime | None = None,
    http_client: Callable[[str, float], dict[str, Any]] = http_get,
) -> tuple[list[dict], dict]:
    section = _section(cfg)
    if section.get("enabled", True) is False:
        return [_finding("n12.koali_system.disabled", "SKIP", "configuration", "Koali system diagnostics are disabled.")], {"enabled": False}

    koali_root = resolve_koali_root(cfg)
    state_root = resolve_state_root(cfg, koali_root)
    findings: list[dict] = []
    metrics: dict[str, Any] = {"enabled": True, "koali_root": str(koali_root), "state_root": str(state_root)}

    if not koali_root.is_dir():
        findings.append(_finding(
            "n12.koali.root", "BLOCKED", "configuration",
            "Koali Spaces repository root is unavailable.", path=str(koali_root),
            recommendation="Set koali_system.root to C:\\mycode\\kOA-Linux\\koali-spaces or the equivalent local path.",
        ))
        return findings, metrics

    findings.append(_finding("n12.koali.root", "PASS", "configuration", "Koali Spaces repository root is available.", path=str(koali_root)))

    launcher_markers = section.get("launcher_markers", ["RUN_KOALI.cmd", "KOALI.pyw"])
    if not isinstance(launcher_markers, list):
        launcher_markers = []
    missing_launchers = [str(item) for item in launcher_markers if not (koali_root / str(item)).is_file()]
    findings.append(_finding(
        "n12.launcher.contract",
        "PASS" if not missing_launchers else "FAIL",
        "runtime",
        "Koali managed launcher contract is installed." if not missing_launchers else "Koali managed launcher files are missing.",
        evidence={"required": launcher_markers, "missing": missing_launchers},
    ))

    state_files = {
        "ecosystem": state_root / "ecosystem-status.json",
        "surface": state_root / "surface-runtime.json",
        "active": state_root / "active-state.json",
    }
    missing_state = [name for name, path in state_files.items() if not path.is_file()]
    if missing_state:
        findings.append(_finding(
            "n12.state.files", "BLOCKED", "runtime",
            "Koali live state files are incomplete.",
            evidence={"missing": missing_state, "state_root": str(state_root)},
            recommendation="Launch Koali with RUN_KOALI.cmd and wait for the ecosystem state compiler.",
        ))
        return findings, metrics

    findings.append(_finding("n12.state.files", "PASS", "runtime", "Koali live state files are present.", evidence={k: str(v) for k, v in state_files.items()}))

    try:
        ecosystem = _read_json(state_files["ecosystem"])
        surface = _read_json(state_files["surface"])
        active = _read_json(state_files["active"])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append(_finding("n12.state.parse", "INFRA_ERROR", "runtime", "Koali live state could not be parsed.", evidence=f"{type(exc).__name__}: {exc}"))
        return findings, metrics

    state_findings, state_metrics = evaluate_loaded_state(
        cfg, koali_root=koali_root, ecosystem=ecosystem, surface=surface, active=active, now=now
    )
    findings.extend(state_findings)
    metrics.update(state_metrics)

    expected_sources = _expected_sources(section)
    if expected_sources:
        discovered_sources = _by((ecosystem.get("discovery") or {}).get("sources", []), "id") if isinstance(ecosystem.get("discovery"), dict) else {}
        for policy in expected_sources:
            source_id = str(policy.get("id"))
            required = bool(policy.get("required", True))
            source = discovered_sources.get(source_id)
            if source is None or source.get("found") is not True:
                findings.append(_finding(
                    f"n12.source.{source_id}.discovery",
                    "FAIL" if required else "PASS",
                    "integration",
                    f"Required Koali source '{source_id}' is not discoverable." if required else f"Optional reference source '{source_id}' is absent, which is accepted.",
                    evidence={"required": required, "found": False},
                ))
                continue
            reference_expected = policy.get("reference_only")
            boundary_ok = True if reference_expected is None else source.get("referenceOnly") is bool(reference_expected)
            qualification = source.get("qualification") if isinstance(source.get("qualification"), dict) else {}
            expected_state = policy.get("qualification_state")
            qualification_ok = True if not expected_state else str(qualification.get("state")) == str(expected_state)
            ok = boundary_ok and qualification_ok
            findings.append(_finding(
                f"n12.source.{source_id}.policy",
                "PASS" if ok else ("FAIL" if required else "WARN"),
                "integration",
                f"Koali source '{source_id}' satisfies its discovery/boundary/qualification policy." if ok else f"Koali source '{source_id}' diverges from its expected policy.",
                evidence={"found": True, "referenceOnly": source.get("referenceOnly"), "expectedReferenceOnly": reference_expected, "qualificationState": qualification.get("state"), "expectedQualificationState": expected_state},
            ))

    if section.get("live_http", True):
        timeout = float(section.get("probe_timeout_seconds", 3))
        shell_url = str(section.get("shell_url", "http://127.0.0.1:4173")).rstrip("/")
        shell_probe = http_client(shell_url + "/", timeout)
        findings.append(_finding(
            "n12.shell.http",
            "PASS" if shell_probe.get("ok") else "FAIL",
            "runtime",
            "Koali presentation endpoint is reachable." if shell_probe.get("ok") else "Koali presentation endpoint is unreachable.",
            evidence={k: v for k, v in shell_probe.items() if k != "body"},
        ))

        state_path = str(section.get("shell_state_endpoint", "/api/shell-state"))
        public_probe = http_client(shell_url + (state_path if state_path.startswith("/") else "/" + state_path), timeout)
        public_state: dict | None = None
        if public_probe.get("ok"):
            try:
                decoded = json.loads(str(public_probe.get("body") or ""))
                if isinstance(decoded, dict):
                    public_state = decoded
            except json.JSONDecodeError:
                public_state = None
        findings.append(_finding(
            "n12.shell.api",
            "PASS" if public_state is not None else "FAIL",
            "runtime",
            "Public /api/shell-state endpoint returns canonical JSON."
            if public_state is not None else "Public /api/shell-state endpoint did not return usable JSON.",
            evidence={k: v for k, v in public_probe.items() if k != "body"},
        ))
        if public_state is not None:
            expected_modules = set(_module_ids(active))
            public_modules = set(_module_ids(public_state))
            public_ready = public_state.get("state") == "ready"
            findings.append(_finding(
                "n12.shell.api_projection",
                "PASS" if public_ready and expected_modules == public_modules else "FAIL",
                "presentation",
                "Public shell API matches the canonical ready projection."
                if public_ready and expected_modules == public_modules
                else "Public shell API diverges from the canonical active-state projection.",
                evidence={
                    "state": public_state.get("state"),
                    "canonical_modules": sorted(expected_modules),
                    "public_modules": sorted(public_modules),
                },
            ))
            findings.extend(_public_shell_privacy_findings(public_state))

        runtimes = ecosystem.get("runtimes", {}) if isinstance(ecosystem.get("runtimes"), dict) else {}
        for item in _expected_products(section):
            product_id, _module_id, _shell_critical, allow_unready, _presentation = _product_policy(item)
            runtime = runtimes.get(product_id) if isinstance(runtimes.get(product_id), dict) else {}
            probes = runtime.get("probes", []) if isinstance(runtime.get("probes"), list) else []
            required_probes = [probe for probe in probes if isinstance(probe, dict) and probe.get("required") is True and isinstance(probe.get("url"), str)]
            if not required_probes:
                findings.append(_finding(
                    f"n12.product.{product_id}.live_probes", "PARTIAL", "runtime",
                    "No independently testable required HTTP probe was declared for this product."
                ))
                continue
            live_results = [http_client(str(probe["url"]), timeout) for probe in required_probes]
            all_ready = all(result.get("ok") for result in live_results)
            accepted = all_ready or allow_unready
            findings.append(_finding(
                f"n12.product.{product_id}.live_probes",
                "PASS" if all_ready else ("WARN" if allow_unready else "FAIL"),
                "runtime",
                f"Independent live probes for '{product_id}' are reachable."
                if all_ready else (
                    f"Independent live probes for optional '{product_id}' are unavailable as currently accepted."
                    if allow_unready else f"One or more independent live probes for '{product_id}' failed."
                ),
                evidence=[{k: v for k, v in result.items() if k != "body"} for result in live_results],
            ))

    else:
        findings.append(_finding(
            "n12.live_http.coverage", "PARTIAL", "runtime",
            "Live HTTP checks are disabled; state-file checks do not establish live availability."
        ))
    metrics["live_http_checked"] = bool(section.get("live_http", True))
    metrics["finding_count"] = len(findings)
    return findings, metrics


def run_koali_system_diagnostics(cfg: dict, report) -> None:
    findings, metrics = collect_koali_system_findings(cfg)
    report.metrics["koali_system"] = metrics
    for item in findings:
        report.add(
            item["id"], item["verdict"], item["category"], item["message"],
            evidence=item.get("evidence"), recommendation=item.get("recommendation"), path=item.get("path"),
        )
