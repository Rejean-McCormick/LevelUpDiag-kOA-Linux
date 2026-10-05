# N14 — Koali Final Integration Delta

N14 is a read-only diagnostic for the parts of the finalized Koali integration that are not established by already-green component suites.

It verifies catalog topology, web/headless owner roles, required source authorities, Kristal reference-only policy, absence of Diag products, bootstrap contract/evidence, launcher files/ports, and Médiathèque sibling-instance persistence.

A successful `CHECK_KOALI.cmd` alone is not accepted as final bootstrap evidence: N14 requires a real bootstrap status with `checkOnly=false` and all required events `ready`.
