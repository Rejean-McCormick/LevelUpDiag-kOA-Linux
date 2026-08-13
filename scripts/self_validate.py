"""End-to-end self-validation gate for LevelUpDiag-Koali.

This script validates the diagnostic tool itself before it is trusted to assess
a kOA-Linux checkout.  Synthetic execution probes use temporary repositories
and targets; they never depend on or modify a real kOA-Linux checkout.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from levelupdiag_core.artifacts import level_artifacts_dir
from levelupdiag_core.commands import run_cmd
from levelupdiag_core.config import AppConfig
from levelupdiag_core.manifest import LevelInfo, get_level
from levelupdiag_core.runner import run_campaign
from levelupdiag_core.verdicts import (
    BLOCKED,
    CONFIG_ERROR,
    FAIL,
    INFRA_ERROR,
    PASS,
    aggregate_verdicts,
    exit_code,
)

_GUI_BLOCKED_EXIT = 20


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One independently reportable self-validation observation."""

    name: str
    verdict: str
    detail: str = ""


def _python_command(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def _run_process(
    command: Sequence[str],
    *,
    timeout: float = 120,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(ROOT),
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
        check=False,
    )


def _last_lines(text: str, count: int = 8) -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[-count:])


def _process_check(
    name: str,
    command: Sequence[str],
    *,
    timeout: float = 120,
    success_text: str | None = None,
) -> CheckResult:
    try:
        completed = _run_process(command, timeout=timeout)
    except subprocess.TimeoutExpired:
        return CheckResult(name, INFRA_ERROR, f"timed out after {timeout:g}s")
    except OSError as exc:
        return CheckResult(name, INFRA_ERROR, f"{type(exc).__name__}: {exc}")

    output = completed.stdout or ""
    if completed.returncode != 0:
        return CheckResult(
            name,
            FAIL,
            f"exit={completed.returncode}; {_last_lines(output)}",
        )
    if success_text is not None and success_text not in output:
        return CheckResult(
            name,
            FAIL,
            f"expected output marker {success_text!r} was not produced",
        )
    return CheckResult(name, PASS, _last_lines(output) or "completed successfully")


def check_repository_verifier() -> CheckResult:
    return _process_check(
        "repository architecture",
        _python_command("scripts/verify_repo.py"),
        success_text="repository verification: PASS",
    )


def check_manifest_cli() -> CheckResult:
    result = _process_check(
        "CLI manifest listing",
        _python_command("scripts/run_level.py", "--list"),
    )
    if result.verdict != PASS:
        return result

    completed = _run_process(_python_command("scripts/run_level.py", "--list"))
    output = completed.stdout or ""
    if "N00" not in output or "N11" not in output:
        return CheckResult(
            "CLI manifest listing",
            FAIL,
            "manifest listing did not expose both N00 and N11",
        )
    return CheckResult("CLI manifest listing", PASS, "N00..N11 manifest is listable")


def check_pytest_suite() -> CheckResult:
    env = dict(os.environ)
    try:
        completed = _run_process(
            _python_command("-m", "pytest", "-q"),
            timeout=180,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("pytest suite", INFRA_ERROR, "pytest timed out after 180s")
    except OSError as exc:
        return CheckResult("pytest suite", INFRA_ERROR, f"{type(exc).__name__}: {exc}")

    if completed.returncode != 0:
        return CheckResult(
            "pytest suite",
            FAIL,
            f"exit={completed.returncode}; {_last_lines(completed.stdout or '', 12)}",
        )
    return CheckResult("pytest suite", PASS, _last_lines(completed.stdout or ""))


def check_command_pass() -> CheckResult:
    result = run_cmd(
        _python_command("-c", "print('self-validation-pass')"),
        cwd=ROOT,
        timeout=5,
        name="self-validation-pass",
    )
    ok = (
        result.verdict == PASS
        and result.exit_code == 0
        and "self-validation-pass" in result.output_tail
    )
    return CheckResult(
        "synthetic command PASS",
        PASS if ok else FAIL,
        f"verdict={result.verdict}, exit={result.exit_code}",
    )


def check_command_fail() -> CheckResult:
    result = run_cmd(
        _python_command(
            "-c",
            "import sys; print('self-validation-fail'); sys.exit(7)",
        ),
        cwd=ROOT,
        timeout=5,
        name="self-validation-fail",
    )
    ok = (
        result.verdict == FAIL
        and result.exit_code == 7
        and "self-validation-fail" in result.output_tail
    )
    return CheckResult(
        "synthetic command FAIL",
        PASS if ok else FAIL,
        f"observed verdict={result.verdict}, exit={result.exit_code}",
    )


def check_missing_executable() -> CheckResult:
    result = run_cmd(
        ["levelupdiag-self-validation-missing-executable-9d5b59"],
        cwd=ROOT,
        timeout=5,
        name="missing-executable",
    )
    ok = result.verdict in {BLOCKED, INFRA_ERROR} and result.exit_code is None
    return CheckResult(
        "synthetic missing executable",
        PASS if ok else FAIL,
        f"observed verdict={result.verdict}, exit={result.exit_code}",
    )


def check_timeout() -> CheckResult:
    result = run_cmd(
        _python_command(
            "-c",
            "import time; print('before-timeout', flush=True); time.sleep(5)",
        ),
        cwd=ROOT,
        timeout=0.5,
        name="timeout-probe",
    )
    ok = (
        result.verdict == INFRA_ERROR
        and result.exit_code is None
        and "before-timeout" in result.output_tail
        and result.error is not None
    )
    return CheckResult(
        "synthetic timeout",
        PASS if ok else FAIL,
        f"observed verdict={result.verdict}, exit={result.exit_code}",
    )


def _copy_manifest(destination_root: Path) -> None:
    shutil.copyfile(ROOT / "levelupdiag_manifest.json", destination_root / "levelupdiag_manifest.json")


def _synthetic_config(root: Path) -> AppConfig:
    target = root / "target"
    target.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        diagnostics_repo_root=str(root),
        target_repo_root=str(target),
        control_dir=".levelupdiag",
        artifacts_dir=".levelupdiag/diagnostics",
    )


def _write_fake_level(
    root: Path,
    level: LevelInfo,
    *,
    verdict: str,
    output: str = "",
    marker: Path | None = None,
) -> Path:
    path = root / level.file
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "from levelupdiag_core.models import LevelResult",
        f"LEVEL_ID = {level.id!r}",
        f"LEVEL_NAME = {level.name!r}",
        "def run(config=None):",
    ]
    if marker is not None:
        lines.append(
            f"    open({str(marker)!r}, 'w', encoding='utf-8').write('executed')"
        )
    lines.append(
        "    return LevelResult("
        f"level=LEVEL_ID, name=LEVEL_NAME, verdict={verdict!r}, output_tail={output!r})"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def check_synthetic_pass_campaign() -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="levelupdiag-self-pass-") as temporary:
        root = Path(temporary)
        _copy_manifest(root)
        config = _synthetic_config(root)
        level = get_level("N01", root)
        _write_fake_level(root, level, verdict=PASS, output="synthetic campaign pass")

        campaign = run_campaign("self-validation-pass", ["N01"], config)
        run_id = campaign.metadata.get("run_id")
        if not isinstance(run_id, str):
            return CheckResult("synthetic PASS campaign", FAIL, "campaign has no string run_id")

        summary_dir = config.control_root_path / "runs" / run_id
        level_root = level_artifacts_dir(config.artifacts_root_path, level.id, level.name)
        run_dirs = [path for path in level_root.iterdir() if path.is_dir()]
        required_files = [
            summary_dir / "summary.json",
            summary_dir / "summary.txt",
        ]
        if len(run_dirs) == 1:
            required_files.extend([run_dirs[0] / "result.json", run_dirs[0] / "output.log"])

        ok = (
            campaign.verdict == PASS
            and [item.verdict for item in campaign.levels] == [PASS]
            and len(run_dirs) == 1
            and all(path.is_file() for path in required_files)
            and "synthetic campaign pass"
            in (run_dirs[0] / "output.log").read_text(encoding="utf-8")
        )
        return CheckResult(
            "synthetic PASS campaign",
            PASS if ok else FAIL,
            "campaign, result.json, output.log, summary.json and summary.txt verified",
        )


def check_dependency_blocking() -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="levelupdiag-self-blocked-") as temporary:
        root = Path(temporary)
        _copy_manifest(root)
        config = _synthetic_config(root)
        first = get_level("N01", root)
        second = get_level("N02", root)
        marker = root / "n02-executed.txt"
        _write_fake_level(root, first, verdict=FAIL, output="dependency failed")
        _write_fake_level(root, second, verdict=PASS, marker=marker)

        campaign = run_campaign("self-validation-blocking", ["N02"], config)
        observed = [item.verdict for item in campaign.levels]
        ok = observed == [FAIL, BLOCKED] and campaign.verdict == BLOCKED and not marker.exists()
        return CheckResult(
            "dependency BLOCKED propagation",
            PASS if ok else FAIL,
            f"observed={observed}, campaign={campaign.verdict}, dependent_executed={marker.exists()}",
        )


def check_missing_level_file() -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="levelupdiag-self-missing-level-") as temporary:
        root = Path(temporary)
        _copy_manifest(root)
        config = _synthetic_config(root)
        campaign = run_campaign("self-validation-missing-level", ["N01"], config)
        observed = campaign.levels[0].verdict if campaign.levels else "NONE"
        ok = observed == CONFIG_ERROR and campaign.verdict == CONFIG_ERROR
        return CheckResult(
            "missing level file -> CONFIG_ERROR",
            PASS if ok else FAIL,
            f"observed={observed}, campaign={campaign.verdict}",
        )


def _load_delivery_level():
    source = ROOT / "levels" / "N11_delivery.pyw"
    loader = SourceFileLoader("_levelupdiag_self_validation_n11", str(source))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise ImportError(f"cannot create import spec for {source}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@contextmanager
def _environment_value(name: str, value: str | None) -> Iterator[None]:
    previous = os.environ.get(name)
    existed = name in os.environ
    try:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        yield
    finally:
        if existed and previous is not None:
            os.environ[name] = previous
        else:
            os.environ.pop(name, None)


def check_delivery_clean_and_contaminated() -> CheckResult:
    module = _load_delivery_level()
    with tempfile.TemporaryDirectory(prefix="levelupdiag-self-delivery-") as temporary:
        root = Path(temporary)
        config = AppConfig(
            diagnostics_repo_root=str(root),
            target_repo_root=str(root / "target"),
        )
        clean = root / "clean-delivery"
        clean.mkdir()
        (clean / "koa-tool").write_text("safe", encoding="utf-8")

        contaminated = root / "contaminated-delivery"
        residue = contaminated / "tools" / "levelupdiag_core"
        residue.mkdir(parents=True)
        (residue / "commands.py").write_text("", encoding="utf-8")

        with _environment_value("LEVELUPDIAG_DELIVERY_TARGET", str(clean)):
            clean_result = module.run(config)
        with _environment_value("LEVELUPDIAG_DELIVERY_TARGET", str(contaminated)):
            contaminated_result = module.run(config)

        ok = clean_result.verdict == PASS and contaminated_result.verdict == FAIL
        return CheckResult(
            "N11 clean/contaminated delivery",
            PASS if ok else FAIL,
            f"clean={clean_result.verdict}, contaminated={contaminated_result.verdict}",
        )


def check_gui_import() -> CheckResult:
    probe = r'''
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
root = Path.cwd()
source = root / "levelupdiag_wrapper.pyw"
loader = SourceFileLoader("_levelupdiag_gui_import_probe", str(source))
spec = importlib.util.spec_from_loader(loader.name, loader)
if spec is None:
    raise SystemExit("cannot build wrapper import spec")
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
assert callable(module.create_app)
assert callable(module.main)
print("GUI import PASS")
'''
    return _process_check(
        "GUI import/no autorun",
        _python_command("-c", probe),
        timeout=15,
        success_text="GUI import PASS",
    )


def check_gui_open() -> CheckResult:
    probe = rf'''
import importlib.util
import sys
import tkinter as tk
from importlib.machinery import SourceFileLoader
from pathlib import Path
import levelupdiag_core.runner as runner
calls = []
def forbidden(*args, **kwargs):
    calls.append((args, kwargs))
    raise RuntimeError("campaign execution occurred during GUI startup")
runner.run_level = forbidden
runner.run_levels = forbidden
source = Path.cwd() / "levelupdiag_wrapper.pyw"
loader = SourceFileLoader("_levelupdiag_gui_open_probe", str(source))
spec = importlib.util.spec_from_loader(loader.name, loader)
if spec is None:
    raise SystemExit(3)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
try:
    root, app = module.create_app()
except tk.TclError as exc:
    print(f"GUI smoke BLOCKED: {{exc}}")
    raise SystemExit({_GUI_BLOCKED_EXIT})
root.update_idletasks()
root.destroy()
if calls:
    print("GUI startup executed a level/campaign")
    raise SystemExit(1)
print("GUI open PASS")
'''
    try:
        completed = _run_process(_python_command("-c", probe), timeout=20)
    except subprocess.TimeoutExpired:
        return CheckResult("GUI open smoke", INFRA_ERROR, "GUI smoke probe timed out")
    except OSError as exc:
        return CheckResult("GUI open smoke", INFRA_ERROR, f"{type(exc).__name__}: {exc}")

    output = completed.stdout or ""
    if completed.returncode == 0 and "GUI open PASS" in output:
        return CheckResult("GUI open smoke", PASS, "window created/destroyed without autorun")
    if completed.returncode == _GUI_BLOCKED_EXIT:
        return CheckResult("GUI open smoke", BLOCKED, _last_lines(output))
    return CheckResult(
        "GUI open smoke",
        FAIL,
        f"exit={completed.returncode}; {_last_lines(output)}",
    )


def run_self_validation(
    *,
    include_pytest: bool = True,
    include_gui_open: bool = True,
) -> list[CheckResult]:
    """Run the complete LevelUpDiag self-validation matrix."""

    checks = [
        check_repository_verifier,
        check_manifest_cli,
        check_command_pass,
        check_command_fail,
        check_missing_executable,
        check_timeout,
        check_synthetic_pass_campaign,
        check_dependency_blocking,
        check_missing_level_file,
        check_delivery_clean_and_contaminated,
        check_gui_import,
    ]
    results = [check() for check in checks]
    if include_pytest:
        results.insert(2, check_pytest_suite())
    if include_gui_open:
        results.append(check_gui_open())
    return results


def overall_verdict(results: Iterable[CheckResult]) -> str:
    verdicts = [result.verdict for result in results]
    if not verdicts:
        return CONFIG_ERROR
    return aggregate_verdicts(verdicts)


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Validate LevelUpDiag-Koali itself before using it to validate kOA-Linux."
    )


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    results = run_self_validation()
    width = max(len(result.name) for result in results)
    print("LevelUpDiag-Koali self-validation")
    print()
    for result in results:
        detail = f" — {result.detail}" if result.detail else ""
        print(f"[{result.verdict:<12}] {result.name:<{width}}{detail}")

    verdict = overall_verdict(results)
    print()
    print(f"SELF VALIDATION: {verdict}")
    return exit_code(verdict, strict_warn=True)


if __name__ == "__main__":
    raise SystemExit(main())
