# Security model

- Diagnostic target defaults to the parent repository and can be overridden explicitly.
- Subprocesses execute with argument vectors and `shell=false`.
- Generated evidence lives under `.levelupdiag/`.
- Captured command output is bounded.
- Common passwords, secrets, API keys, access/auth tokens, and bearer tokens are redacted.
- Referenced Koali gate reports are read only if they resolve inside the target repository, live below a `koa-ci-evidence` path component, and end with `-gate-report.json`.
- Repository scans do not need to follow file symlinks.
- The campaign runner snapshots tracked Git state before and after diagnostics and reports `ERROR` if tracked state changes.
- N11 explicitly checks that diagnostic residue does not enter a delivery directory or supported archive.
