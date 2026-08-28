from __future__ import annotations

import importlib.util
import io
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
import tarfile
import zipfile

from levelupdiag_core.config import AppConfig
from levelupdiag_core.verdicts import BLOCKED, CONFIG_ERROR, FAIL, PASS

ROOT = Path(__file__).resolve().parents[1]
LEVEL_PATH = ROOT / "levels" / "N11_delivery.pyw"


def _load_level():
    loader = SourceFileLoader("ldk_test_n11_delivery", str(LEVEL_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _config(tmp_path: Path, *, delivery_target: str | None = None) -> AppConfig:
    raw = {}
    if delivery_target is not None:
        raw["delivery_target"] = delivery_target
    return AppConfig(
        diagnostics_repo_root=str(tmp_path),
        target_repo_root=str(tmp_path / "koa-linux"),
        raw=raw,
    )


def test_clean_directory_passes(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery"
    (delivery / "bin").mkdir(parents=True)
    (delivery / "bin" / "koa-tool").write_text("safe", encoding="utf-8")
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(delivery))

    result = module.run(_config(tmp_path))

    assert result.verdict == PASS
    assert result.metadata["residue_count"] == 0


def test_contaminated_directory_fails(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery"
    residue = delivery / "tools" / "levelupdiag_core"
    residue.mkdir(parents=True)
    (residue / "commands.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(delivery))

    result = module.run(_config(tmp_path))

    assert result.verdict == FAIL
    assert result.findings
    assert any("levelupdiag_core" in (finding.path or "") for finding in result.findings)


def test_clean_zip_passes_without_extraction(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery.zip"
    with zipfile.ZipFile(delivery, "w") as archive:
        archive.writestr("usr/bin/koa-tool", "safe")
        archive.writestr("etc/koa/config.toml", "safe")
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(delivery))

    result = module.run(_config(tmp_path))

    assert result.verdict == PASS
    assert not (tmp_path / "usr").exists()


def test_contaminated_zip_fails_without_extraction(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery.zip"
    with zipfile.ZipFile(delivery, "w") as archive:
        archive.writestr("opt/tools/levelupdiag_manifest.json", "{}")
        archive.writestr("usr/bin/koa-tool", "safe")
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(delivery))

    result = module.run(_config(tmp_path))

    assert result.verdict == FAIL
    assert any(finding.path == "opt/tools/levelupdiag_manifest.json" for finding in result.findings)
    assert not (tmp_path / "opt").exists()


def test_clean_tar_passes_without_extraction(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery.tar"
    with tarfile.open(delivery, "w") as archive:
        payload = b"safe"
        info = tarfile.TarInfo("usr/bin/koa-tool")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(delivery))

    result = module.run(_config(tmp_path))

    assert result.verdict == PASS
    assert not (tmp_path / "usr").exists()


def test_contaminated_tar_fails_without_extraction(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery.tar"
    with tarfile.open(delivery, "w") as archive:
        payload = b"{}"
        info = tarfile.TarInfo("opt/tools/levelupdiag_manifest.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(delivery))

    result = module.run(_config(tmp_path))

    assert result.verdict == FAIL
    assert any(finding.path == "opt/tools/levelupdiag_manifest.json" for finding in result.findings)
    assert not (tmp_path / "opt").exists()


def test_missing_target_is_config_error(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    monkeypatch.delenv("LEVELUPDIAG_DELIVERY_TARGET", raising=False)

    result = module.run(_config(tmp_path))

    assert result.verdict == CONFIG_ERROR
    assert result.findings[0].id == "n11.delivery.target-not-configured"


def test_config_fallback_is_used(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery"
    delivery.mkdir()
    monkeypatch.delenv("LEVELUPDIAG_DELIVERY_TARGET", raising=False)

    result = module.run(_config(tmp_path, delivery_target=str(delivery)))

    assert result.verdict == PASS


def test_environment_target_precedes_config_fallback(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    clean = tmp_path / "clean"
    clean.mkdir()
    contaminated = tmp_path / "contaminated"
    (contaminated / ".levelupdiag").mkdir(parents=True)
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(clean))

    result = module.run(_config(tmp_path, delivery_target=str(contaminated)))

    assert result.verdict == PASS


def test_regular_non_zip_file_is_blocked(tmp_path: Path, monkeypatch) -> None:
    module = _load_level()
    delivery = tmp_path / "delivery.bin"
    delivery.write_bytes(b"not a zip")
    monkeypatch.setenv("LEVELUPDIAG_DELIVERY_TARGET", str(delivery))

    result = module.run(_config(tmp_path))

    assert result.verdict == BLOCKED
