# Result model

Level verdicts: `PASS`, `WARN`, `FAIL`, `SKIP`, `BLOCKED`, `PARTIAL`, `ERROR`, `INFRA_ERROR`, `CONFIG_ERROR`.

For Koali:

- `FAIL`: an executed target validator returned a functional failure.
- `SKIP`: an optional Koali validator is not configured.
- `BLOCKED`: prerequisite evidence is unavailable or a Koali public gate explicitly reports a blocked condition.
- `INFRA_ERROR`: a command could not complete because of execution infrastructure such as a timeout or launch failure.
- `CONFIG_ERROR`: the LevelUpDiag setup or a required command is invalid/missing.

The structured command evidence is stored in each level `result.json`; separate legacy `output.log` files are intentionally not produced.
