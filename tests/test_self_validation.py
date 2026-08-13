from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

from levelupdiag_core.verdicts import BLOCKED, FAIL, PASS

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "self_validate.py"


def _load_self_validate():
    loader = SourceFileLoader("levelupdiag_test_self_validate", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def self_validate():
    return _load_self_validate()


def test_command_outcome_probes(self_validate) -> None:
    assert self_validate.check_command_pass().verdict == PASS
    assert self_validate.check_command_fail().verdict == PASS
    assert self_validate.check_missing_executable().verdict == PASS
    assert self_validate.check_timeout().verdict == PASS


def test_synthetic_pass_campaign_writes_canonical_outputs(self_validate) -> None:
    result = self_validate.check_synthetic_pass_campaign()

    assert result.verdict == PASS
    assert "result.json" in result.detail
    assert "output.log" in result.detail
    assert "summary.json" in result.detail
    assert "summary.txt" in result.detail


def test_dependency_failure_blocks_dependent_level(self_validate) -> None:
    result = self_validate.check_dependency_blocking()

    assert result.verdict == PASS
    assert "BLOCKED" in result.detail
    assert "dependent_executed=False" in result.detail


def test_missing_level_file_is_detected_as_configuration_error(self_validate) -> None:
    result = self_validate.check_missing_level_file()

    assert result.verdict == PASS
    assert "CONFIG_ERROR" in result.detail


def test_delivery_probe_distinguishes_clean_and_contaminated(self_validate) -> None:
    result = self_validate.check_delivery_clean_and_contaminated()

    assert result.verdict == PASS
    assert "clean=PASS" in result.detail
    assert "contaminated=FAIL" in result.detail


def test_gui_import_probe_is_headless_safe(self_validate) -> None:
    result = self_validate.check_gui_import()

    assert result.verdict == PASS


def test_overall_verdict_never_converts_failure_or_block_to_pass(self_validate) -> None:
    check = self_validate.CheckResult

    assert self_validate.overall_verdict([check("ok", PASS)]) == PASS
    assert self_validate.overall_verdict([check("ok", PASS), check("bad", FAIL)]) == FAIL
    assert self_validate.overall_verdict([check("ok", PASS), check("blocked", BLOCKED)]) == BLOCKED


def test_self_validation_matrix_without_nested_pytest_or_display(self_validate) -> None:
    results = self_validate.run_self_validation(
        include_pytest=False,
        include_gui_open=False,
    )

    assert results
    assert all(result.verdict == PASS for result in results), [
        (result.name, result.verdict, result.detail) for result in results
    ]
