from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from .koali_system_support import _finding, resolve_koali_root


def _section(cfg: dict) -> dict:
    value = cfg.get("koali_final", {})
    return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _mycode_root(koali_root: Path) -> Path:
    # Expected deployed layout: C:\\mycode\\kOA-Linux\\koali-spaces.
    # Keep this derivation structural so the diagnostic also works on another drive.
    parents = koali_root.parents
    return parents[1] if len(parents) >= 2 else koali_root.parent


def _catalog_findings(koali_root: Path, section: dict) -> tuple[list[dict], dict[str, Any]]:
    findings: list[dict] = []
    metrics: dict[str, Any] = {}
    rel = str(section.get("catalog", "config/ecosystem.catalog.json"))
    path = koali_root / rel
    if not path.is_file():
        return [_finding("n14.catalog.file", "FAIL", "integration", "Koali ecosystem catalog is missing.", path=str(path))], metrics
    try:
        catalog = _read_json(path)
    except Exception as exc:
        return [_finding("n14.catalog.parse", "INFRA_ERROR", "integration", "Koali ecosystem catalog is not parseable.", evidence=f"{type(exc).__name__}: {exc}", path=str(path))], metrics

    findings.append(_finding("n14.catalog.file", "PASS", "integration", "Koali ecosystem catalog is present and parseable.", path=str(path)))
    products = {str(item.get("id")): item for item in catalog.get("products", []) if isinstance(item, dict) and item.get("id")}
    sources = {str(item.get("id")): item for item in catalog.get("sources", []) if isinstance(item, dict) and item.get("id")}
    expected_products = section.get("required_products", {}) if isinstance(section.get("required_products"), dict) else {}
    expected_sources = section.get("required_sources", []) if isinstance(section.get("required_sources"), list) else []
    metrics["catalog_products"] = sorted(products)
    metrics["catalog_sources"] = sorted(sources)

    missing = sorted(set(expected_products) - set(products))
    findings.append(_finding(
        "n14.catalog.required_products",
        "PASS" if not missing else "FAIL",
        "integration",
        "All final Koali products are declared in the catalog." if not missing else "The final Koali catalog is missing required products.",
        evidence={"expected": sorted(expected_products), "missing": missing},
    ))

    for product_id, policy in expected_products.items():
        item = products.get(product_id)
        if not isinstance(item, dict):
            continue
        expected_shell = bool(policy.get("affects_shell_state", False)) if isinstance(policy, dict) else False
        ok = item.get("requiredForBootstrap") is True and bool(item.get("affectsShellState", True)) == expected_shell
        findings.append(_finding(
            f"n14.catalog.product.{product_id}.policy",
            "PASS" if ok else "FAIL",
            "integration",
            f"Bootstrap/shell policy for '{product_id}' matches the finalized topology." if ok else f"Bootstrap/shell policy for '{product_id}' diverges from the finalized topology.",
            evidence={"requiredForBootstrap": item.get("requiredForBootstrap"), "affectsShellState": item.get("affectsShellState", True), "expectedAffectsShellState": expected_shell},
        ))

    required_source_ids = {str(x) for x in expected_sources}
    missing_sources = sorted(required_source_ids - set(sources))
    not_required = sorted(source_id for source_id in required_source_ids if source_id in sources and sources[source_id].get("requiredForBootstrap") is not True)
    findings.append(_finding(
        "n14.catalog.required_sources",
        "PASS" if not missing_sources and not not_required else "FAIL",
        "integration",
        "All final source/runtime authorities are required by bootstrap." if not missing_sources and not not_required else "Required source/runtime authorities are incomplete in the catalog.",
        evidence={"expected": sorted(required_source_ids), "missing": missing_sources, "not_required": not_required},
    ))

    kristal = sources.get("kristal_framework")
    kristal_ok = isinstance(kristal, dict) and kristal.get("referenceOnly") is True and kristal.get("requiredForBootstrap") is not True and kristal.get("integrationMode") == "reference_only"
    findings.append(_finding(
        "n14.catalog.kristal_boundary",
        "PASS" if kristal_ok else "FAIL",
        "boundary",
        "Kristal remains reference-only and outside the operational bootstrap." if kristal_ok else "Kristal catalog policy no longer matches the reference-only boundary.",
        evidence=kristal,
    ))

    diag_products = sorted(product_id for product_id in products if "diag" in product_id.casefold())
    findings.append(_finding(
        "n14.catalog.no_diag_products",
        "PASS" if not diag_products else "FAIL",
        "boundary",
        "No diagnostic repository is onboarded as a Koali product." if not diag_products else "A diagnostic repository is incorrectly onboarded as a Koali product.",
        evidence={"diag_products": diag_products},
    ))
    return findings, metrics


def _owner_contract_findings(mycode: Path, section: dict) -> list[dict]:
    findings: list[dict] = []
    contracts = section.get("owner_contracts", {}) if isinstance(section.get("owner_contracts"), dict) else {}
    for product_id, spec in contracts.items():
        if not isinstance(spec, dict):
            continue
        rel = str(spec.get("path", ""))
        path = mycode / Path(rel.replace("\\", os.sep).replace("/", os.sep))
        if not path.is_file():
            findings.append(_finding(f"n14.contract.{product_id}", "FAIL", "integration", f"Owner contract for '{product_id}' is missing.", path=str(path)))
            continue
        try:
            contract = _read_json(path)
        except Exception as exc:
            findings.append(_finding(f"n14.contract.{product_id}", "INFRA_ERROR", "integration", f"Owner contract for '{product_id}' is not parseable.", evidence=f"{type(exc).__name__}: {exc}", path=str(path)))
            continue
        expected_surface = str(spec.get("surface", "web"))
        surface = contract.get("surface", {}) if isinstance(contract.get("surface"), dict) else {}
        actual_surface = "headless" if surface.get("mode") == "headless" else "web"
        probes = [probe for probe in contract.get("probes", []) if isinstance(probe, dict) and probe.get("required") is True]
        ok = contract.get("productId") == product_id and actual_surface == expected_surface and len(probes) >= 1
        findings.append(_finding(
            f"n14.contract.{product_id}",
            "PASS" if ok else "FAIL",
            "integration",
            f"Owner contract '{product_id}' matches its finalized surface/runtime role." if ok else f"Owner contract '{product_id}' diverges from its finalized role.",
            evidence={"productId": contract.get("productId"), "surface": actual_surface, "expectedSurface": expected_surface, "requiredProbeCount": len(probes)},
            path=str(path),
        ))
    return findings


def _bootstrap_findings(koali_root: Path, mycode: Path, section: dict) -> list[dict]:
    findings: list[dict] = []
    bootstrap_rel = str(section.get("bootstrap_script", "scripts/bootstrap-koali.ps1"))
    bootstrap_script = koali_root / bootstrap_rel
    if not bootstrap_script.is_file():
        findings.append(_finding("n14.bootstrap.script", "FAIL", "bootstrap", "Koali bootstrap script is missing.", path=str(bootstrap_script)))
    else:
        text = bootstrap_script.read_text(encoding="utf-8-sig", errors="replace")
        required_tokens = [str(x) for x in section.get("bootstrap_contract_tokens", []) if str(x)]
        absent = [token for token in required_tokens if token not in text]
        findings.append(_finding(
            "n14.bootstrap.script",
            "PASS" if not absent else "FAIL",
            "bootstrap",
            "Bootstrap contract contains the finalized runtime/dependency provisions." if not absent else "Bootstrap script is missing finalized provisions.",
            evidence={"missing_tokens": absent},
            path=str(bootstrap_script),
        ))

    status_rel = str(section.get("bootstrap_status", ".koali-dev/bootstrap/bootstrap-status.json"))
    status_path = koali_root / status_rel
    if not status_path.is_file():
        findings.append(_finding(
            "n14.bootstrap.status", "BLOCKED", "bootstrap",
            "No completed Koali bootstrap status is available yet.", path=str(status_path),
            recommendation="Run START_KOALI.cmd once on Windows, then rerun the final LevelUpDiag campaign.",
        ))
        return findings
    try:
        status = _read_json(status_path)
    except Exception as exc:
        findings.append(_finding("n14.bootstrap.status", "INFRA_ERROR", "bootstrap", "Bootstrap status cannot be parsed.", evidence=f"{type(exc).__name__}: {exc}", path=str(status_path)))
        return findings

    events = {str(item.get("name")): item for item in status.get("events", []) if isinstance(item, dict) and item.get("name")}
    expected_events = [str(x) for x in section.get("required_bootstrap_events", []) if str(x)]
    missing = [name for name in expected_events if name not in events]
    bad = [name for name in expected_events if name in events and str(events[name].get("state")) != "ready"]
    expected_mycode = str(mycode.resolve(strict=False)).casefold()
    recorded_mycode = str(status.get("mycode") or "").casefold()
    root_ok = bool(recorded_mycode) and Path(str(status.get("mycode"))).resolve(strict=False) == mycode.resolve(strict=False)
    # On Windows resolve/case behavior can vary with drive casing; keep a textual fallback.
    root_ok = root_ok or (recorded_mycode.replace("/", "\\") == expected_mycode.replace("/", "\\"))
    ok = not missing and not bad and root_ok and status.get("checkOnly") is False
    findings.append(_finding(
        "n14.bootstrap.status",
        "PASS" if ok else "FAIL",
        "bootstrap",
        "A real (non-check-only) bootstrap completed with every required event ready." if ok else "The recorded bootstrap does not prove a complete finalized installation.",
        evidence={"checkOnly": status.get("checkOnly"), "missing_events": missing, "non_ready_events": bad, "recorded_mycode": status.get("mycode"), "expected_mycode": str(mycode)},
        recommendation=None if ok else "Run START_KOALI.cmd to complete provisioning; do not use CHECK_KOALI.cmd as the only bootstrap evidence.",
        path=str(status_path),
    ))
    return findings


def _mediatheque_findings(mycode: Path, section: dict) -> list[dict]:
    med = section.get("mediatheque", {}) if isinstance(section.get("mediatheque"), dict) else {}
    engine = mycode / Path(str(med.get("engine", "kOA_Mediatheque/mediatheque")).replace("/", os.sep))
    instance = mycode / Path(str(med.get("instance", "kOA_Mediatheque/mediatheque-blank")).replace("/", os.sep))
    config = instance / str(med.get("config", "mediatheque.instance.toml"))
    db = instance / str(med.get("database", "01_DB/koa_mediatheque.sqlite"))
    sibling_ok = engine.is_dir() and instance.is_dir() and engine.parent == instance.parent and engine != instance and config.is_file()
    findings = [_finding(
        "n14.mediatheque.boundary",
        "PASS" if sibling_ok else "FAIL",
        "storage",
        "Médiathèque engine and persistent blank instance remain separate sibling roots." if sibling_ok else "Médiathèque engine/instance separation is not intact.",
        evidence={"engine": str(engine), "instance": str(instance), "config": str(config)},
    )]
    if not db.is_file():
        findings.append(_finding("n14.mediatheque.database", "BLOCKED", "storage", "Persistent Médiathèque SQLite database has not been initialized.", path=str(db), recommendation="Run START_KOALI.cmd once to initialize the sibling instance."))
        return findings
    try:
        with sqlite3.connect(str(db)) as conn:
            row = conn.execute("select value from schema_meta where key='schema_version'").fetchone()
        version = str(row[0]) if row else ""
        ok = bool(version)
        findings.append(_finding(
            "n14.mediatheque.database", "PASS" if ok else "FAIL", "storage",
            f"Persistent Médiathèque database is initialized (schema {version})." if ok else "Médiathèque database is missing schema metadata.",
            evidence={"schema_version": version, "database": str(db)}, path=str(db),
        ))
    except Exception as exc:
        findings.append(_finding("n14.mediatheque.database", "FAIL", "storage", "Médiathèque database cannot be opened/read as the persistent instance.", evidence=f"{type(exc).__name__}: {exc}", path=str(db)))
    return findings


def _launcher_findings(koali_root: Path, section: dict) -> list[dict]:
    findings: list[dict] = []
    markers = [str(x) for x in section.get("launcher_markers", []) if str(x)]
    missing = [marker for marker in markers if not (koali_root / marker).is_file()]
    findings.append(_finding(
        "n14.launcher.files", "PASS" if not missing else "FAIL", "lifecycle",
        "Final Koali start/check/stop launcher set is installed." if not missing else "Final Koali launcher set is incomplete.",
        evidence={"required": markers, "missing": missing},
    ))
    config_path = koali_root / "launcher" / "launcher-config.json"
    if config_path.is_file():
        try:
            value = _read_json(config_path)
            reserved = {int(x) for x in value.get("reservedPorts", [])}
            expected = {int(x) for x in section.get("expected_reserved_ports", [])}
            missing_ports = sorted(expected - reserved)
            stale = sorted(reserved - expected)
            findings.append(_finding(
                "n14.launcher.ports",
                "PASS" if not missing_ports else "FAIL",
                "lifecycle",
                "All finalized Koali ports are protected by the launcher." if not missing_ports else "Launcher reserved-port policy misses finalized service ports.",
                evidence={"expected": sorted(expected), "missing": missing_ports, "extra_reserved": stale},
                recommendation="Extra reserved ports are informational; remove them only if they are confirmed legacy and unused." if stale else None,
            ))
        except Exception as exc:
            findings.append(_finding("n14.launcher.ports", "INFRA_ERROR", "lifecycle", "Launcher config cannot be parsed.", evidence=f"{type(exc).__name__}: {exc}", path=str(config_path)))
    else:
        findings.append(_finding("n14.launcher.ports", "FAIL", "lifecycle", "Launcher config is missing.", path=str(config_path)))

    if os.name == "nt":
        tools = {name: shutil.which(name) for name in ("powershell.exe", "node.exe", "uv.exe")}
        findings.append(_finding(
            "n14.host.toolchain",
            "PASS" if all(tools.values()) else "FAIL",
            "environment",
            "Windows host exposes the minimum Koali bootstrap toolchain." if all(tools.values()) else "Windows host is missing one or more minimum Koali bootstrap tools.",
            evidence=tools,
        ))
    else:
        findings.append(_finding("n14.host.toolchain", "SKIP", "environment", "Windows-native bootstrap toolchain check is only meaningful on the target Windows host."))
    return findings


def collect_koali_final_findings(cfg: dict) -> tuple[list[dict], dict]:
    section = _section(cfg)
    if section.get("enabled", True) is False:
        return [_finding("n14.koali_final.disabled", "SKIP", "configuration", "Final Koali delta diagnostics are disabled.")], {"enabled": False}
    koali_root = resolve_koali_root(cfg)
    mycode = _mycode_root(koali_root)
    metrics: dict[str, Any] = {"enabled": True, "koali_root": str(koali_root), "mycode_root": str(mycode)}
    if not koali_root.is_dir():
        return [_finding("n14.koali.root", "BLOCKED", "configuration", "Koali root is unavailable for final-delta qualification.", path=str(koali_root))], metrics
    findings = [_finding("n14.koali.root", "PASS", "configuration", "Koali root is available for final-delta qualification.", path=str(koali_root))]
    catalog_findings, catalog_metrics = _catalog_findings(koali_root, section)
    findings.extend(catalog_findings)
    metrics.update(catalog_metrics)
    findings.extend(_owner_contract_findings(mycode, section))
    findings.extend(_bootstrap_findings(koali_root, mycode, section))
    findings.extend(_mediatheque_findings(mycode, section))
    findings.extend(_launcher_findings(koali_root, section))
    metrics["finding_count"] = len(findings)
    return findings, metrics


def run_koali_final_diagnostics(cfg: dict, report) -> None:
    findings, metrics = collect_koali_final_findings(cfg)
    report.metrics["koali_final"] = metrics
    for item in findings:
        report.add(
            item["id"], item["verdict"], item["category"], item["message"],
            evidence=item.get("evidence"), recommendation=item.get("recommendation"), path=item.get("path"),
        )
