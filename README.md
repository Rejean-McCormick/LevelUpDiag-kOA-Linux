# LevelUpDiag-Koali v3.0

LevelUpDiag-Koali 3.0 targets the **final Koali integration**, without replaying component test suites that are already known green.

The default campaign is now:

```text
koali-final = N00 + N12 + N14
```

- **N00 Diagnostic Integrity** verifies that the diagnostic frame itself is trustworthy.
- **N12 Koali Product System** validates the live Koali state, six required owner products, loopback probes, source qualification, public shell projection, and web/headless boundaries.
- **N14 Koali Final Integration Delta** validates the remaining one-click integration risks: final catalog topology, owner contracts, bootstrap evidence, launcher contract, reserved service ports, Kristal reference-only policy, no Diag onboarding, and Médiathèque engine/instance persistence.

It intentionally does **not** run the legacy kOA component/security/offline/system suites unless you explicitly select those campaigns.

## Final product policy

```text
Orgo                required / web / shell-critical
Orgo Worlds         required / web / shell-critical
SemantiK Architect  required / headless / not projected as UI
Médiathèque kOA     required / web / shell-critical
Konfid               required / headless / not projected as UI
Kor                  required / headless / not projected as UI
```

Required source/runtime authorities:

```text
Médiathèque blank instance
kOA Linux
Koali Control Panel
kOA Digital Ecosystem
Interaction Kernel
SemantiK Runtime Orchestrator
```

Kristal Framework is accepted only as `reference_only`; it is not part of operational bootstrap. Diagnostic repositories must not be onboarded as Koali products.

## Run

First start Koali normally on Windows:

```bat
C:\mycode\kOA-Linux\koali-spaces\START_KOALI.cmd
```

Then run LevelUpDiag from its sibling repository:

```bat
C:\mycode\kOA-Linux\LevelUpDiag-Koali\RUN_KOALI_FINAL_DIAG.cmd
```

or:

```bat
python levelupdiag.py run koali-final
```

The desktop console `LEVELUPDIAG_CONSOLE.pyw` defaults to **KOALI FINAL**.

## What N12 proves

N12 reads Koali's canonical `.koali-dev/state` projection and independently probes required loopback endpoints. It verifies:

- all six products are discovered with valid owner contracts;
- all six required runtimes are `ready`;
- Orgo, Orgo Worlds, and Médiathèque are projected as owner-controlled web surfaces;
- SemantiK Architect, Konfid, and Kor remain headless and are **not** projected as fake UI modules;
- the public `/api/shell-state` matches the canonical projection without leaking orchestration-private fields;
- required source/runtime authorities are found and qualified;
- an optional Kristal repository, if present, remains reference-only.

A headless runtime may be non-shell-critical, but because it is part of the finalized bootstrap profile its runtime outage still fails N12. `affectsShellState=false` only means the public shell projection itself need not become degraded.

## What N14 proves

N14 is deliberately narrow. It checks the things that were not established by the already-green internal suites:

- exact finalized catalog policy and required products/sources;
- owner contract roles (`web` versus `headless`) and required readiness probes;
- Kristal reference-only boundary and absence of Diag products;
- the Windows bootstrap script still contains the required Node/uv/Python 3.12/3.13/3.14, Interaction Kernel, Kor, Médiathèque, and local Orgo/PGlite provisions;
- a **real non-CheckOnly bootstrap** has produced `.koali-dev/bootstrap/bootstrap-status.json` with every required event `ready`;
- `START_KOALI.cmd`, `CHECK_KOALI.cmd`, `STOP_KOALI.cmd`, and `KOALI.pyw` are installed;
- finalized service ports are protected by the launcher;
- Médiathèque code and its `mediatheque-blank` data instance remain separate sibling roots, and the persistent SQLite database is initialized.

N14 is read-only. It does not install dependencies, restart Koali, delete files, or mutate product data.

## Campaigns

The current Koali-focused campaigns are:

- `koali-final` — default, N00 + N12 + N14, VALIDATION.
- `koali-final-debug` — same targeted checks, DEBUG aggregation.
- `koali-system` — N00 + N12 live system only.
- `koali-system-debug` — N00 + N12 live system only, DEBUG.
- `store` — independent N00 + N13 third-party/store diagnostics.

Historical kOA-Linux campaigns (`stabilization`, `debug`, `validation`, `release`, etc.) remain available for explicit use. They are no longer the default because they would replay known component work unrelated to the final Koali integration delta.

## Repository layout

Expected layout:

```text
C:\mycode\
├── Interaction-Kernel\interaction_kernel\
├── Konfid\konfid\
├── Kor\kor\
├── Orgo\Orgo\
├── Orgo\Orgo_Worlds\
├── SemantiK_Architect\SemantiK_Architect\
├── SemantiK_Architect\SemantiK_Runtime_Orchestrator\
├── kOA_Mediatheque\mediatheque\
├── kOA_Mediatheque\mediatheque-blank\
└── kOA-Linux\
    ├── koa-linux\
    ├── koali-spaces\
    ├── Koali-Control-Panel\
    └── LevelUpDiag-Koali\
```

LevelUpDiag remains an external diagnostic specialization. It is not onboarded into Koali as a product.

## Evidence

Reports remain under the selected target repository in `.levelupdiag/`. The final campaign reports both execution verdict and system findings; a `BLOCKED` bootstrap-status finding means Koali has not yet produced real first-run bootstrap evidence on that Windows installation.

## Version 3.0

Version 3.0 aligns LevelUpDiag with the finalized Koali topology after the cumulative integration work. It removes Konnaxion/Ariane from the active Koali-system expectation, makes all six supplied products required, understands headless owner products correctly, qualifies required source/runtime authorities, and adds N14 so the remaining Windows/bootstrap/storage risks can be checked without rerunning already-green product suites.
