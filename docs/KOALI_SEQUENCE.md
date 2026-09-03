# Koali diagnostic sequence

| Order | Level | Required | Koali behavior |
|---:|---|:---:|---|
| 0 | N00 Diagnostic Integrity | yes | validates the LevelUpDiag frame and sequence contract |
| 10 | N01 Environment | yes | target path, Python, required/optional tools |
| 20 | N02 Repository | yes | Git worktree, branch/HEAD, dirty state |
| 30 | N03 Documentation | yes | `docs/tools/validate_docs.py` |
| 40 | N04 Contracts | yes | contracts public gate + referenced gate evidence |
| 50 | N05 Components | yes | components public gate + referenced gate evidence |
| 60 | N06 Integrations | no | configured public integration gate when available |
| 70 | N07 Profiles | no | `uv run --frozen pytest -q tests/profiles` |
| 80 | N08 Security | no | security gate, `security: blocked` normalization |
| 90 | N09 Offline | no | offline gate, `offline: blocked` normalization |
| 100 | N10 System | no | system gate, `system: blocked` normalization |
| 110 | N11 Delivery | no | confirms LevelUpDiag is absent from delivery output |

All levels execute serially. A normal functional failure can be followed by later independent evidence; a hard prerequisite failure blocks explicitly dependent levels.
