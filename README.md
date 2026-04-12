# Prime Canon Freeze-Ready Artifact Pack

This repository is a minimal, buildable control-plane starter for a graph-first, repo-native prime canon system.

It freezes:

- exact JSON Schemas for the core object families
- a single canonical object envelope
- a minimal repo layout
- example control objects
- example runtime objects
- a local validator
- a GitHub Actions validation workflow

## Fast start

```bash
# machine: <your-machine>
mkdir -p ~/src/prime-canon
cd ~/src/prime-canon

# unpack the artifact pack here, then:
python3 -m pip install --upgrade pyyaml jsonschema
python3 scripts/validate_pack.py .
```

## Canonical object envelope

Every object uses the same top-level shape:

```yaml
kind: PRIME_CANON_<FAMILY>_V1
version: v1
metadata:
  object_id: ...
  display_name: ...
  created_at: ...
  created_by: ...
attributes:
  identity: ...
  lineage: ...
  evidence: ...
  governance: ...
  semantic: ...
  relational: ...
  operational: ...
  temporal: ...
spec:
  ...
```

## Minimal object families in this pack

Control-plane surfaces:

- `PRIME_CANON_REPO_MANIFEST_V1`
- `PRIME_CANON_ATTRIBUTE_DICTIONARY_V1`
- `PRIME_CANON_FORMULA_PROFILE_V1`
- `PRIME_CANON_ADMISSIBILITY_PROFILE_V1`
- `PRIME_CANON_JURISDICTION_BINDING_V1`
- `PRIME_CANON_LANE_MANIFEST_V1`

Runtime surfaces:

- `PRIME_CANON_CORPUS_INDEX_V1`
- `PRIME_CANON_SOURCE_UNIT_V1`
- `PRIME_CANON_CANDIDATE_CLAIM_V1`
- `PRIME_CANON_EVIDENCE_LINK_V1`
- `PRIME_CANON_ADMISSIBILITY_DECISION_V1`
- `PRIME_CANON_FORMULA_EVAL_RECEIPT_V1`
- `PRIME_CANON_CONTRADICTION_BUNDLE_V1`
- `PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1`
- `PRIME_CANON_SUPERSESSION_EDGE_V1`
- `PRIME_CANON_NODE_V1`
- `PRIME_CANON_PROMOTION_READINESS_PACKET_V1`
- `PRIME_CANON_REPLAY_MANIFEST_V1`
- `PRIME_CANON_CURRENT_STATE_VIEW_V1`

## Validation surfaces

Local:

```bash
# machine: <your-machine>
python3 scripts/validate_pack.py .
```

Makefile:

```bash
# machine: <your-machine>
make deps
make validate
```

CI:

- `.github/workflows/validate-prime-canon.yml`

## Suggested first implementation sequence

1. Freeze `control/` and `schemas/`.
2. Validate the pack with `scripts/validate_pack.py`.
3. Replace the example subject under `canon/` with a real subject corpus.
4. Keep receipts append-only.
5. Treat `views/rendered/` as projection only.
6. Add compilers after the object model is accepted.

## File guide

- `FREEZE_ORDER.md`
- `docs/OBJECT_DEFINITIONS.md`
- `docs/MINIMAL_REPO_LAYOUT.md`
- `TREE.txt`
