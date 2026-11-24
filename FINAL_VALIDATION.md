# LevelUpDiag-Koali 3.0 validation

- Internal test suite: **62/62 PASS** (historical result; retained as prior evidence).
- Python compileall: PASS.
- Manifest exposes `koali-final = N00 + N12 + N14`.
- N12 updated to six required products and explicit web/headless semantics.
- N14 added for finalized catalog, bootstrap evidence, owner contracts, launcher/ports, Kristal boundary, no-Diag onboarding, and Mediatheque persistent sibling instance.
- Static N14 run against the integrated Koali workspace passes all code/catalog/contract/launcher boundaries; bootstrap-status and persistent SQLite are intentionally BLOCKED there because the packaged Linux workspace has not undergone the real first Windows bootstrap.

The intended final acceptance run is on the Windows host after `START_KOALI.cmd`: `RUN_KOALI_FINAL_DIAG.cmd`.

## Local audit recheck — 2026-11-23

On the supplied 2026-11-23 snapshot, the audit executed:

```bash
python -m unittest discover -s tests -q
```

**Result: 63 tests passed (0 failures).** This count supersedes the old headline for the **current observed test suite**, without retroactively rewriting the earlier 62/62 run. It is a code-level local check, not a final Windows host, QEMU or deployment qualification. The final `koali-final` acceptance campaign still requires its real host/runtime context.
