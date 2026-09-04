# LevelUpDiag-Koali v2.1

LevelUpDiag-Koali 2.1 is a **debug-first** diagnostic suite for kOA-Linux.
Its primary rule is:

> If a formality does not materially prevent observation or execution of the system, it must not block DEBUG.

Repository cleanliness, frozen architecture conformance, documentation conformance, delivery residue, signatures, and release provenance remain available as validation/finalization evidence, but they are no longer prerequisites for the main debug path.


## Repository layout

The specialization remains a sibling of the kOA-Linux repository:

```text
C:\mycode\kOA-Linux\
├── koa-linux\
└── LevelUpDiag-Koali\
```

The default target is `../koa-linux`.

Local developer utilities such as `GitSink.bat` are not a DEBUG gate. If an underlying kOA conformance validator reports a local utility or generated build residue, that individual level may report `FAIL/WARN`, but DEBUG continues collecting independent functional/runtime evidence.

## Modes

### DEBUG — default

Use while developing, loading, testing, or diagnosing kOA-Linux.

- no tracked-Git-state protection;
- no dependency verdict blocks another level;
- repository/documentation/release formalities are excluded from the default campaign;
- `FAIL`, `BLOCKED`, `CONFIG_ERROR`, `SKIP`, and `PARTIAL` remain visible at their local level but make the campaign `WARN`, not globally `BLOCKED`;
- `ERROR`/`INFRA_ERROR` still mean the diagnostic execution itself had a problem.

### VALIDATION

Use to check repository/documentation/conformance in addition to functional gates.
Dependencies can be blocked by `BLOCKED`, `ERROR`, `INFRA_ERROR`, or `CONFIG_ERROR`, but a clean Git worktree is not imposed globally.

### RELEASE

Use for strict finalization. Tracked Git state is snapshotted before and after the campaign; mutation by diagnostics is an error.

## Normal execution

```bash
python levelupdiag.py doctor
python levelupdiag.py list
python levelupdiag.py run debug
```

Explicit modes are supported:

```bash
python levelupdiag.py run N08,N09,N10 --mode debug
python levelupdiag.py run validation --mode validation
python levelupdiag.py run release --mode release
```

Windows launcher default:

```bat
RUN_LEVELUPDIAG.bat
```

Linux/macOS launcher default:

```bash
./RUN_LEVELUPDIAG.sh
```

Both now default to the `debug` campaign.

## Console

`LEVELUPDIAG_CONSOLE.pyw` exposes three policies:

- **DEBUG — non bloquant**
- **VALIDATION — conformité**
- **RELEASE — strict**

Presets:

- **DEBUG PRINCIPAL**: N00, N01, N04-N10
- **STRUCTURE / CONFORMITÉ**: N00-N03
- **VALIDATION**: N00-N10
- **FINALISATION**: N00-N11

N02 Repository and N03 Documentation are intentionally absent from DEBUG PRINCIPAL.

## Level sequence

```text
N00 Diagnostic Integrity
N01 Environment
N02 Repository / Structure
N03 Documentation
N04 Contracts
N05 Components
N06 Integrations
N07 Profiles
N08 Security Runtime
N09 Offline Runtime
N10 System Runtime
N11 Delivery
```

All levels remain serial for stable evidence ordering.

Functional levels no longer depend transitively on N02. Selecting `N08,N09,N10` adds functional prerequisites N00, N01, N04 and N05, but not repository/documentation formalities.

## Campaigns

- `debug` — primary development diagnosis, mode DEBUG.
- `structure` — repository/documentation checks, mode VALIDATION.
- `validation` — N00-N10, mode VALIDATION.
- `release` — N00-N11, mode RELEASE.

Compatibility aliases remain: `preflight`, `core`, `standard`, `delivery`, `full`.

## Result model

A campaign summary now separates:

```text
verdict
execution_verdict
system testability
conformance_verdict
```

In DEBUG, conformance is reported as `NOT_EVALUATED` by the campaign summary. Local level findings are still preserved exactly.

Example:

```text
LevelUpDiag debug [DEBUG] - WARN
Diagnostic execution: PASS
System testability: PARTIAL
Conformance: NOT_EVALUATED
```

That means the diagnostic completed and found unavailable/failed local checks; it does **not** mean the whole debug session is blocked.

## Git policy

DEBUG does not inspect Git globally before/after a run. N02 performs Git observations only when N02 is explicitly selected.
A dirty worktree in N02 is advisory in DEBUG.

RELEASE retains tracked-state mutation protection because release/finalization provenance is a separate concern.

## kOA-specific validation commands

Default commands are still the canonical public kOA-Linux vectors:

```text
Documentation  uv run --frozen python docs/tools/validate_docs.py
Contracts      uv run --frozen python ci/scripts/run-contracts.py
Components     uv run --frozen python ci/scripts/run-components.py
Profiles       uv run --frozen pytest -q tests/profiles
Security       uv run --frozen python ci/scripts/run-security.py
Offline        uv run --frozen python ci/scripts/run-offline.py
System         uv run --frozen python ci/scripts/run-system-tests.py
```

Koali gate markers such as `security: blocked`, `offline: blocked`, and `system: blocked` remain local level verdicts. In DEBUG they do not prevent independent levels from running.

## Evidence

Evidence remains under the target repository:

```text
.levelupdiag/
├── runs/<run-id>/
│   ├── effective_config.json
│   ├── summary.json
│   ├── summary.txt
│   └── levels/Nxx/result.json
└── latest/
```

Commands use `shell=false`; output is bounded and redacted; target mutation remains disabled by configuration.
