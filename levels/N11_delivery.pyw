"""N11 — verify that LevelUpDiag-Koali is absent from a delivery target."""

from __future__ import annotations

import os
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from levelupdiag_core.config import AppConfig, load_config
from levelupdiag_core.logs import run_directory, update_latest, write_output_log
from levelupdiag_core.manifest import get_level
from levelupdiag_core.models import Finding, LevelResult
from levelupdiag_core.reports import write_level_result
from levelupdiag_core.verdicts import BLOCKED, CONFIG_ERROR, FAIL, INFRA_ERROR, PASS, exit_code

LEVEL_ID = "N11"
LEVEL_NAME = "Delivery"
_DELIVERY_ENV = "LEVELUPDIAG_DELIVERY_TARGET"
_SIGNATURES = (
    "levelupdiag-koali",
    "levelupdiag_core",
    ".levelupdiag",
    "levelupdiag_manifest.json",
    "levelupdiag.config.example.json",
    "levelupdiag.config.local.json",
    "levelupdiag_wrapper.pyw",
    "levelupdiag_wrapper_common.py",
    "start_levelupdiag.bat",
)


def _delivery_target(config: AppConfig) -> Path | None:
    raw = os.environ.get(_DELIVERY_ENV, "").strip()
    if not raw:
        configured = config.get("delivery_target")
        if isinstance(configured, str):
            raw = configured.strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = config.diagnostics_root_path / path
    return path.resolve()


def _matching_signature(path_text: str) -> str | None:
    normalized = path_text.replace("\\", "/").strip("/")
    if not normalized:
        return None
    parts = [part.casefold() for part in PurePosixPath(normalized).parts]
    for signature in _SIGNATURES:
        folded = signature.casefold()
        if folded in parts:
            return signature
    return None


def _scan_directory(target: Path) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    root_signature = _matching_signature(target.name)
    if root_signature:
        matches.append((target.name, root_signature))
    for current, directories, files in os.walk(target, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            path = current_path / name
            relative = path.relative_to(target).as_posix()
            signature = _matching_signature(relative)
            if signature:
                matches.append((relative, signature))
    return matches


def _scan_zip(target: Path) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    with zipfile.ZipFile(target, "r") as archive:
        for info in archive.infolist():
            signature = _matching_signature(info.filename)
            if signature:
                matches.append((info.filename, signature))
    return matches


def _scan_tar(target: Path) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    with tarfile.open(target, "r:*") as archive:
        for member in archive:
            signature = _matching_signature(member.name)
            if signature:
                matches.append((member.name, signature))
    return matches


def _failure_result(target: Path, matches: list[tuple[str, str]], started: datetime) -> LevelResult:
    ended = datetime.now().astimezone()
    findings = [
        Finding(
            id=f"n11.delivery.residue.{index:03d}",
            severity=FAIL,
            message=f"LevelUpDiag-Koali delivery residue detected: {relative}",
            category="delivery",
            path=relative,
            evidence=f"matched signature: {signature}",
            recommendation="Remove the appendix from the delivery staging area and rebuild the artifact.",
        )
        for index, (relative, signature) in enumerate(matches, start=1)
    ]
    return LevelResult(
        level=LEVEL_ID,
        name=LEVEL_NAME,
        verdict=FAIL,
        findings=findings,
        started_at=started.isoformat(timespec="seconds"),
        ended_at=ended.isoformat(timespec="seconds"),
        duration_seconds=(ended - started).total_seconds(),
        cwd=str(target),
        output_tail="\n".join(relative for relative, _ in matches[-20:]),
        metadata={"delivery_target": str(target), "residue_count": len(matches)},
    )


def run(config: AppConfig | None = None) -> LevelResult:
    cfg = config if config is not None else load_config()
    started = datetime.now().astimezone()
    target = _delivery_target(cfg)
    if target is None:
        return LevelResult(
            level=LEVEL_ID,
            name=LEVEL_NAME,
            verdict=CONFIG_ERROR,
            findings=[
                Finding(
                    id="n11.delivery.target-not-configured",
                    severity=CONFIG_ERROR,
                    message=(
                        "No delivery target is configured. Set LEVELUPDIAG_DELIVERY_TARGET "
                        "or provide delivery_target in the local configuration."
                    ),
                    category="configuration",
                )
            ],
        )
    if not target.exists():
        return LevelResult(
            level=LEVEL_ID,
            name=LEVEL_NAME,
            verdict=CONFIG_ERROR,
            findings=[
                Finding(
                    id="n11.delivery.target-missing",
                    severity=CONFIG_ERROR,
                    message=f"Delivery target does not exist: {target}",
                    category="configuration",
                    path=str(target),
                )
            ],
            cwd=str(target),
        )

    try:
        if target.is_dir():
            matches = _scan_directory(target)
        elif target.is_file() and zipfile.is_zipfile(target):
            matches = _scan_zip(target)
        elif target.is_file() and tarfile.is_tarfile(target):
            matches = _scan_tar(target)
        elif target.is_file():
            return LevelResult(
                level=LEVEL_ID,
                name=LEVEL_NAME,
                verdict=BLOCKED,
                findings=[
                    Finding(
                        id="n11.delivery.unsupported-file",
                        severity=BLOCKED,
                        message="Delivery target is a regular file but not a supported ZIP or TAR archive.",
                        category="delivery",
                        path=str(target),
                        recommendation="Provide a directory, ZIP archive, or TAR archive for inspection.",
                    )
                ],
                cwd=str(target),
            )
        else:
            return LevelResult(
                level=LEVEL_ID,
                name=LEVEL_NAME,
                verdict=BLOCKED,
                findings=[
                    Finding(
                        id="n11.delivery.unsupported-target",
                        severity=BLOCKED,
                        message="Delivery target is neither a directory nor a supported ZIP or TAR archive.",
                        category="delivery",
                        path=str(target),
                    )
                ],
                cwd=str(target),
            )
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        ended = datetime.now().astimezone()
        return LevelResult(
            level=LEVEL_ID,
            name=LEVEL_NAME,
            verdict=INFRA_ERROR,
            findings=[
                Finding(
                    id="n11.delivery.inspection-error",
                    severity=INFRA_ERROR,
                    message=f"Unable to inspect delivery target: {exc}",
                    category="delivery",
                    path=str(target),
                )
            ],
            started_at=started.isoformat(timespec="seconds"),
            ended_at=ended.isoformat(timespec="seconds"),
            duration_seconds=(ended - started).total_seconds(),
            cwd=str(target),
        )

    if matches:
        return _failure_result(target, matches, started)

    ended = datetime.now().astimezone()
    return LevelResult(
        level=LEVEL_ID,
        name=LEVEL_NAME,
        verdict=PASS,
        started_at=started.isoformat(timespec="seconds"),
        ended_at=ended.isoformat(timespec="seconds"),
        duration_seconds=(ended - started).total_seconds(),
        cwd=str(target),
        output_tail="No LevelUpDiag-Koali delivery residue detected.",
        metadata={"delivery_target": str(target), "residue_count": 0},
    )


def main() -> int:
    cfg = load_config()
    started = datetime.now().astimezone()
    result = run(cfg)
    level = get_level(LEVEL_ID, cfg.diagnostics_root_path)
    directory = run_directory(cfg, level, started)
    result_path = write_level_result(result, directory / "result.json")
    write_output_log(directory, result.output_tail)
    update_latest(cfg, level, result_path)
    return exit_code(result.verdict)


if __name__ == "__main__":
    raise SystemExit(main())
