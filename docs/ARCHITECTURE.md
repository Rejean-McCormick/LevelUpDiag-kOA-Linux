# Architecture — Debug-first policy

LevelUpDiag-Koali separates **observation**, **conformance**, and **release provenance**.

The tool code lives in this directory and generated evidence lives under `.levelupdiag/` in the target. Commands execute with `shell=false`, bounded/redacted output, explicit timeouts, and process isolation.

## DEBUG

DEBUG is the default execution policy. It does not snapshot or compare Git state globally. Dependency verdicts do not suppress downstream diagnostic levels. A local `BLOCKED`, `FAIL`, `CONFIG_ERROR`, or repository formality remains evidence for that level while independent diagnostics continue.

The default `debug` campaign excludes N02 Repository/Structure, N03 Documentation, and N11 Delivery.

## VALIDATION

VALIDATION includes formal conformance levels. Hard prerequisite states (`BLOCKED`, `ERROR`, `INFRA_ERROR`, `CONFIG_ERROR`) can block declared dependants. Git cleanliness is still not a global prerequisite.

## RELEASE

RELEASE enables tracked Git-state protection and strict dependency semantics. This is the only default mode where before/after Git tracked-state comparison is part of campaign integrity.

## Dependency topology

Repository conformance is no longer a functional prerequisite. N04 depends on N01 rather than N02; N05 depends on N01/N04; runtime gates depend on N01/N04/N05. This prevents repository formalities from entering a functional debug selection through transitive dependencies.


## Modular product UI boundary

LevelUpDiag is an observer of Koali product-UI modularity, not the owner of that architecture. N06 can consume an explicit local `ui_modularity` policy and test product availability, product-owned standalone markers, public integrated-contribution markers, and explicitly forbidden private cross-product UI dependency tokens.

The check is intentionally configuration-driven so LevelUpDiag does not hard-code product frameworks or manifest names. Optional product absence is a valid state and reports `PASS` for the removal observation; required product absence can report `BLOCKED`. The core `stabilization` campaign does not select N06, so UI-product lifecycle remains outside core stabilization.
