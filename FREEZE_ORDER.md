# Freeze Order

Freeze these artifacts in order. This is the smallest sequence that gives you a lawful, replayable, repo-native canon control plane.

1. `control/repo.manifest.yaml`
2. `control/attributes/core-attribute-dictionary.yaml`
3. `control/formulas/core-default.yaml`
4. `control/admissibility/core-default.yaml`
5. `control/jurisdictions/*.yaml`
6. `control/lanes/*.yaml`
7. `schemas/prime-canon-bundle.schema.json`
8. `scripts/validate_pack.py`
9. `canon/corpora/**`
10. `canon/source_units/**`
11. `canon/candidate_claims/**`
12. `canon/evidence_links/**`
13. `receipts/immutable/**`
14. `canon/contradictions/**`
15. `canon/supersession/**`
16. `canon/nodes/**`
17. `replay/manifests/**`
18. `views/current/**`

## Freeze rules

- Objects under `receipts/immutable/` are append-only after commit.
- Objects under `views/current/` are derived and may only be updated from a lawful promotion path.
- Objects under `canon/nodes/` may not change without a matching promotion readiness packet and reduction decision receipt.
- `schemas/` and `control/` changes should be reviewed before runtime object changes in the same PR.
