# N12 — Koali Product System

N12 is a read-only live-system diagnostic for the KS4.x Koali composition layer.

It verifies:

1. the Koali repository and managed launcher are present;
2. `ecosystem-status.json`, `surface-runtime.json`, and `active-state.json` exist and are fresh;
3. every expected application remains in its owner repository with a discoverable `koali.integration.json`;
4. Konnaxion, Orgo, and Médiathèque are ready;
5. SemantiK Architect may be unready while remaining linked and visible;
6. every product has a runtime registration and resolved local embed target;
7. owner application manifests expose routes but no redundant Koali sidebar;
8. presentation authority remains presentation-only and does not grant capabilities or perform direct domain writes;
9. the global Shell is `ready` and `online` when all Shell-critical products are ready;
10. `/api/shell-state` matches the canonical active projection and does not expose orchestration-private fields;
11. required runtime probes are independently rechecked over loopback only.

N12 refuses non-loopback HTTP targets. It does not turn `allow_network=false` into general network access.

## Changes in 2.6

Optional runtime outages now report WARN, not PASS. Disabled HTTP checks and
products without independently testable required HTTP probes report PARTIAL.
Loopback restrictions apply to redirects too, and environment HTTP proxies are
disabled for these probes. `koali-system` also runs N13; see [Store tests](STORE_TESTS.md).
