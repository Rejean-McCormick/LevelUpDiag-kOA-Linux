# Koali sequence — LevelUpDiag 2.5

## Primary path: live Koali product system

Start Koali with its managed launcher, wait for the Shell to become available, then run:

```text
RUN_KOALI.cmd
→ LevelUpDiag koali-system
→ N00 Diagnostic Integrity
→ N12 Koali Product System
→ N13 Store and Third-Party Applications
```

N12 consumes the runtime evidence produced by Koali itself:

```text
.koali-dev/state/ecosystem-status.json
.koali-dev/state/surface-runtime.json
.koali-dev/state/active-state.json
        ↓
owner contracts + surface projection + module health
        ↓
/api/shell-state + independent loopback probes
```

The expected KS4.4 policy is:

- Konnaxion, Orgo and Médiathèque kOA are Shell-critical and must be ready.
- SemantiK Architect remains linked/projected but its current runtime outage is accepted and must not degrade the global Shell.
- Kristal, kOA Linux, Koali Control Panel and kOA Digital Ecosystem remain source-only discoveries.
- Koali must not expose repository paths, commands, PIDs or other orchestration-private fields through the public Shell state.
- Hosted applications keep their own internal navigation; Koali must not recreate a redundant product sidebar.

## Legacy path: kOA core stabilization

The historical campaigns remain available unchanged for the underlying kOA-Linux target:

```text
stabilization
stabilization-runtime
audit-total
validation
release
```

These continue to use N01-N11 and the WSL/native toolchain rules documented by the kOA-Linux qualification flow.

N13 checks koa-linux store sources by default; Linux session checks are opt-in. See [Store tests](STORE_TESTS.md).
