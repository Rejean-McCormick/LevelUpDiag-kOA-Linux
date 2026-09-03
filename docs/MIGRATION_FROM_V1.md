# Migration from LevelUpDiag-Koali v1

## Preserved

- N00-N11 identities and primary order.
- Required/optional intent of N01-N11.
- Koali command defaults for docs, contracts, components, security, offline, and system.
- Optional integrations command.
- Fixed N07 profile command using `uv --frozen` and `tests/profiles`.
- Git repository observations.
- missing-Python-module diagnosis.
- trusted `koa-ci-evidence/*-gate-report.json` expansion concept.
- `security: blocked`, `offline: blocked`, and `system: blocked` semantics.
- N11 delivery-residue inspection.

## Replaced by the evolved frame

- old runner/planner/model/report implementations;
- old per-level `.pyw` persistence;
- GUI/control-panel wrapper;
- `logs.py` and historical `output.log` format;
- standalone sibling-repository assumption;
- duplicated level command/parsing code.

The new runner provides isolated workers, campaigns, structured summaries, bounded output, redaction, Git mutation protection, explicit timeouts, and deterministic scheduling.

## Deliberate ordering upgrade

The old manifest allowed several independent levels to be parallelized even though documentation presented N00-N11 as the primary progression. In v2, all Koali levels are `parallel_safe: false`; therefore the visible test sequence is deterministic and is treated as part of the Koali contract.
