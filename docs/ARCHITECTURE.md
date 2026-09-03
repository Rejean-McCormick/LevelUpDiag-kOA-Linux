# Architecture

LevelUpDiag-Koali v2 is a target-specific specialization of the LevelUpDiag v2 copy-in frame.

The diagnostic code lives under `levelupdiag/`; generated evidence lives under `.levelupdiag/` at the kOA-Linux repository root. The target is read-oriented by design. Commands are executed with `shell=false`, outputs are bounded/redacted, and tracked Git state is compared before and after each campaign.

## Execution model

The runner builds a campaign from `levelupdiag_manifest.json`, expands transitive dependencies, then schedules ready levels by `order`.

For Koali every level has `parallel_safe: false`. Therefore only one level is active at a time and the stable N00-N11 order is preserved even if `--jobs` is greater than one.

Dependencies retain their original semantic purpose: they identify evidence that must exist before another level can be meaningful. Ordering alone is not encoded as fake dependencies.

## Result model

Each level emits a normalized v2 JSON result. Campaign verdicts distinguish target failure from missing prerequisites, infrastructure failure, and diagnostic configuration errors.

Historical standalone `.pyw` persistence and `output.log` files have been removed. Command tails and referenced gate evidence are embedded in bounded structured findings instead.
