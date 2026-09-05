# Koali sequence — LevelUpDiag 2.2

## Phase 1: stabilize Koali core

Run `stabilization` first. It validates diagnostic integrity, the complete host/build environment, canonical contracts, and native component validations. Independent subsystems are intentionally deferred and must not be marked pinned or activable unless their real source authority has been integrated and verified.

```text
PREPARE DEVELOPMENT ENVIRONMENT
→ LevelUpDiag stabilization
→ build/verify native Koali components
→ repeat until the environment is stable
```

Deferred during this phase:

- Konnaxion: placeholder until real integration.
- Ariane: integrate and test next.
- Orgo: draft/not admitted.
- Semantik Architect: deferred/not admitted.

## Phase 2: core runtime

When a bootable image exists, run `stabilization-runtime`. N08/N09/N10 remain diagnostic in DEBUG; final-profile blockers remain visible but do not redefine the core-stabilization scope.

## Phase 3: subsystem integration

Integrate each independent subsystem with real source pins, digests, license/documentation evidence, adapter tests, and activation evidence.

## Phase 4: final target

Use `validation` and `release` against the unchanged canonical `sovereign-linux-node` target. No partial conformance is claimed.
