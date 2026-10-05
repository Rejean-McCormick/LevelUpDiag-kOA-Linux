# N12 — Koali Product System (v3.0)

N12 validates the **live** final Koali composition. It does not rerun product unit/integration test suites.

Expected products:

- Orgo — web, shell-critical, required ready.
- Orgo Worlds — web, shell-critical, required ready.
- SemantiK Architect — headless, required ready, no fake UI projection.
- Médiathèque kOA — web, shell-critical, required ready.
- Konfid — headless, required ready, no fake UI projection.
- Kor — headless, required ready, no fake UI projection.

N12 checks canonical state freshness, owner-contract discovery, runtime readiness, web-surface registration only where appropriate, active Space projection, shell health semantics, public `/api/shell-state` privacy and independent loopback probes.

It also checks required source/runtime authorities and their qualification state. Kristal is optional and must remain reference-only if present.

Run after Koali is started:

```bat
python levelupdiag.py run koali-system
```

For the full targeted final integration check, use `koali-final` (N00 + N12 + N14).
