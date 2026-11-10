# Branch 08 — Independent runtime and shell readiness qualification

**Status:** local diagnostic checks; no actual Windows bootstrap or machine activation performed in this branch.

LevelUpDiag-Koali N12 already verifies required owner runtimes, true web/headless product topology, source identity, canonical state, public projection privacy, actual loopback probes, and `module_health` semantics. `affects_shell_state=false` permits the **shell** to remain ready during an optional product outage; it does not make the owner product itself ready. N14 checks the remaining source/bootstrap/instance separation and real `checkOnly=false` bootstrap evidence without executing real installation or deployment.

A new regression fixture in `tests/test_koali_system.py` asserts that a required module with missing `module_health` fails diagnostic qualification even when the top-level shell state claims `ready`. This is the third independent view of the same Koali Spaces producer → Control Panel consumer readiness boundary.

Run: `python -m unittest discover -s tests -q`. To claim actual system readiness, run the owner's `koali-final` campaign against an **installed and started** Koali ecosystem on the named host, preserve exact report hashes and revisions, and distinguish source observation from host evidence.
