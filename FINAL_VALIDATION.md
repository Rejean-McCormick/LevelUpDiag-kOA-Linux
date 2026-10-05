# LevelUpDiag-Koali 3.0 validation

- Internal test suite: **62/62 PASS**.
- Python compileall: PASS.
- Manifest exposes `koali-final = N00 + N12 + N14`.
- N12 updated to six required products and explicit web/headless semantics.
- N14 added for finalized catalog, bootstrap evidence, owner contracts, launcher/ports, Kristal boundary, no-Diag onboarding, and Mediatheque persistent sibling instance.
- Static N14 run against the integrated Koali workspace passes all code/catalog/contract/launcher boundaries; bootstrap-status and persistent SQLite are intentionally BLOCKED there because the packaged Linux workspace has not undergone the real first Windows bootstrap.

The intended final acceptance run is on the Windows host after `START_KOALI.cmd`: `RUN_KOALI_FINAL_DIAG.cmd`.
