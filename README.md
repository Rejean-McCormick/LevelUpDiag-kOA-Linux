# LevelUpDiag-Koali v2

LevelUpDiag-Koali v2 is the upgraded, copy-in diagnostic appendix for **kOA-Linux**.
It uses the evolved LevelUpDiag v2 engine while preserving the Koali-specific diagnostic sequence and gate semantics from the previous suite.

## Installation

Copy this directory as `levelupdiag/` directly into the kOA-Linux repository:

```text
koa-linux/
├── ...
└── levelupdiag/
```

The target repository is then detected automatically as the parent directory.
An explicit target remains possible with `--target`.

## Normal execution

```bash
python levelupdiag/levelupdiag.py doctor
python levelupdiag/levelupdiag.py list
python levelupdiag/levelupdiag.py run preflight
python levelupdiag/levelupdiag.py run core
python levelupdiag/levelupdiag.py run standard
```

Windows:

```bat
levelupdiag\RUN_LEVELUPDIAG.bat standard
```

Linux/macOS:

```bash
./levelupdiag/RUN_LEVELUPDIAG.sh standard
```

## Preserved Koali sequence

The suite deliberately executes serially in this order:

```text
N00 Diagnostic Integrity
N01 Environment
N02 Repository
N03 Documentation
N04 Contracts
N05 Components
N06 Integrations
N07 Profiles
N08 Security
N09 Offline
N10 System
N11 Delivery
```

`standard` runs N00 through N10. `full` also runs N11. `delivery` runs the minimum prerequisites plus N11.

Ordering is enforced independently of dependency semantics: all Koali levels are marked `parallel_safe: false`.
This means the sequence remains stable even when a caller supplies a higher `--jobs` value.

## Koali-specific validations retained

Default commands:

```text
Documentation  python docs/tools/validate_docs.py
Contracts      python ci/scripts/run-contracts.py
Components     python ci/scripts/run-components.py
Integrations   not configured by default
Profiles       uv run --frozen pytest -q tests/profiles
Security       python ci/scripts/run-security.py
Offline        python ci/scripts/run-offline.py
System         python ci/scripts/run-system-tests.py
```

Contracts, Components, Security, Offline, and System can capture explicitly referenced local `koa-ci-evidence/*-gate-report.json` evidence. Referenced files are accepted only when they resolve inside the target repository.

The historical Koali markers remain meaningful:

```text
security: blocked
offline: blocked
system: blocked
```

A failed command containing the corresponding marker is normalized to `BLOCKED` rather than `FAIL`.

The suite also retains detection of `ModuleNotFoundError` output so missing validation-environment modules are reported directly.

## Configuration

Versioned defaults live in `levelupdiag.config.json`.
Machine-specific changes belong in `levelupdiag.config.local.json`, which should not be committed.
See `levelupdiag.config.local.example.json`.

Add the following to the **kOA-Linux root** `.gitignore`:

```gitignore
.levelupdiag/
```

N02 reports a warning when this root ignore rule is missing.

Typical override:

```json
{
  "schema": "levelupdiag.config.v2",
  "commands": {
    "integrations": ["python", "ci/scripts/run-integrations.py"]
  },
  "delivery_target": "dist/koa-linux.zip"
}
```

Commands are argument arrays by default and execute with `shell=false`.
String commands remain accepted for compatibility but arrays are preferred.

## Campaigns

- `preflight`: N00-N02.
- `core`: N00-N05, including all required Koali functional gates.
- `standard`: N00-N10, normal Koali diagnostic campaign.
- `delivery`: N00, N01, N11.
- `full`: N00-N11.

Functional `FAIL` does not automatically stop later independent Koali evidence from being collected. Hard prerequisite failures such as `BLOCKED`, `INFRA_ERROR`, `CONFIG_ERROR`, and diagnostic `ERROR` still block levels that explicitly depend on them.

## Results

The old LevelUpDiag-Koali `logs.py`, per-level `output.log`, GUI wrapper, `.pyw` level persistence, and historical run layout are not carried forward.

New evidence is written under the target repository's ignored `.levelupdiag/` directory:

```text
.levelupdiag/
├── runs/<run-id>/
│   ├── summary.json
│   ├── summary.txt
│   └── levels/Nxx/result.json
└── latest/
```

Outputs are bounded and common secret/token patterns are redacted.
The runner snapshots tracked Git state before and after a campaign and raises an error if diagnostics modify tracked files.

## Delivery check

N11 verifies that a delivery directory, ZIP, or TAR archive does not contain LevelUpDiag residue.
Configure it with either:

```text
LEVELUPDIAG_DELIVERY_TARGET
```

or `delivery_target` in local config.

## Migration principle

This version intentionally preserves **Koali behavior and test ordering**, not the old diagnostic implementation.
See `docs/MIGRATION_FROM_V1.md` for the exact mapping.
