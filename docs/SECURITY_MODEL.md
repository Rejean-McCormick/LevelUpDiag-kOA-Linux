# Security model

LevelUpDiag-Koali remains read-oriented and bounded:

- commands execute as argument arrays with `shell=false`;
- stdout/stderr capture is bounded and redacted;
- target mutation is disabled by default;
- network use is disabled unless explicitly enabled;
- referenced gate reports are accepted only from bounded paths inside the target repository;
- worker timeouts remain explicit.

Git tracked-state protection is now **mode-scoped**:

- DEBUG: disabled; Git provenance is not a prerequisite for diagnosis;
- VALIDATION: disabled globally; N02 can still observe repository state when selected;
- RELEASE: enabled and tracked-state mutation during diagnostics is an error.

This keeps release provenance strict without making Git formalities part of ordinary system debugging.
