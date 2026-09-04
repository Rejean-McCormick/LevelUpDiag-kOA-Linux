# Koali diagnostic sequence

| Order | Level | Role | DEBUG principal |
|---:|---|---|---|
| 0 | N00 Diagnostic Integrity | diagnostic framework | yes |
| 10 | N01 Environment | executable environment | yes |
| 20 | N02 Repository / Structure | conformance / Git observation | no |
| 30 | N03 Documentation | conformance | no |
| 40 | N04 Contracts | functional contract checks | yes |
| 50 | N05 Components | component checks | yes |
| 60 | N06 Integrations | integration checks | yes |
| 70 | N07 Profiles | profile checks | yes |
| 80 | N08 Security Runtime | runtime/security evidence | yes |
| 90 | N09 Offline Runtime | offline evidence | yes |
| 100 | N10 System Runtime | system/QEMU evidence | yes |
| 110 | N11 Delivery | finalization | no |

All levels remain serial to preserve deterministic evidence ordering.

The key v2.1 change is dependency separation: N02/N03 are no longer transitive prerequisites of functional/runtime levels.
