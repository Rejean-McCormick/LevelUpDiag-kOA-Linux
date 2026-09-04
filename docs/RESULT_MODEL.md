# Result model

Level verdicts remain:

`PASS`, `WARN`, `FAIL`, `SKIP`, `BLOCKED`, `PARTIAL`, `ERROR`, `INFRA_ERROR`, `CONFIG_ERROR`.

Their meaning is local to a level. `BLOCKED` means that level could not establish its intended evidence because a prerequisite was unavailable. It does not mean every independent diagnostic must stop.

Campaign summaries add:

- `diagnostic_mode`: `debug`, `validation`, or `release`;
- `execution_verdict`: whether the diagnostic machinery completed without `ERROR`/`INFRA_ERROR`;
- `testability`: `COMPLETE` or `PARTIAL`;
- `conformance_verdict`: `NOT_EVALUATED` in DEBUG, otherwise the strict campaign verdict.

## DEBUG aggregation

- any `ERROR`/`INFRA_ERROR` -> campaign `ERROR`;
- any other non-PASS local verdict -> campaign `WARN`;
- otherwise -> `PASS`.

Thus target failures and missing prerequisites remain visible without turning routine development diagnosis into a global `BLOCKED` state.

## VALIDATION / RELEASE aggregation

Strict evidence semantics are preserved. `FAIL` remains failure, required unavailable evidence can block completion, and configuration/diagnostic errors are not accepted as success.
