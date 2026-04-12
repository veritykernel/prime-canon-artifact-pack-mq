# Minimal Repo Layout

This pack is intentionally small. It freezes only the control-plane surfaces required to stand up a lawful prime canon workflow.

## Directory roles

- `control/` — repo enrollment, attribute dictionary, formula profile, admissibility profile, jurisdictions, and lane contracts.
- `canon/corpora/` — subject intake indexes.
- `canon/source_units/` — normalized ingress slices.
- `canon/candidate_claims/` — candidate canon units.
- `canon/evidence_links/` — claim-to-evidence bindings.
- `canon/contradictions/` — durable conflict state.
- `canon/supersession/` — explicit replacement edges.
- `canon/nodes/` — promoted or historical canon nodes.
- `receipts/immutable/` — append-only decisions, packets, and formula receipts.
- `replay/manifests/` — deterministic replay inputs and expected outputs.
- `views/current/` — derived current-state read model.
- `views/rendered/` — human-readable projections only.
- `schemas/` — exact JSON Schema definitions for every object family.
- `scripts/` — validator entrypoint used locally and in CI.

## Tree

```text
prime-canon-artifact-pack
├── .github
│   └── workflows
│       └── validate-prime-canon.yml
├── canon
│   ├── candidate_claims
│   │   └── example-subject
│   │       ├── claim-0000.yaml
│   │       └── claim-0001.yaml
│   ├── contradictions
│   │   └── example-subject
│   │       └── contradiction-0001.yaml
│   ├── corpora
│   │   └── example-subject
│   │       └── index.yaml
│   ├── evidence_links
│   │   └── example-subject
│   │       ├── link-0000.yaml
│   │       └── link-0001.yaml
│   ├── nodes
│   │   └── example-subject
│   │       ├── node-0000.yaml
│   │       └── node-0001.yaml
│   ├── source_units
│   │   └── example-subject
│   │       ├── unit-0000.yaml
│   │       └── unit-0001.yaml
│   └── supersession
│       └── example-subject
│           └── edge-0001.yaml
├── control
│   ├── admissibility
│   │   └── core-default.yaml
│   ├── attributes
│   │   └── core-attribute-dictionary.yaml
│   ├── formulas
│   │   └── core-default.yaml
│   ├── jurisdictions
│   │   ├── claim-extractor-agent.yaml
│   │   ├── evidence-auditor-agent.yaml
│   │   ├── human-reviewer.yaml
│   │   └── promotion-inspector-agent.yaml
│   ├── lanes
│   │   ├── adjudication.yaml
│   │   ├── drift-monitoring.yaml
│   │   ├── intake.yaml
│   │   ├── promotion.yaml
│   │   └── reduction.yaml
│   └── repo.manifest.yaml
├── docs
│   └── OBJECT_DEFINITIONS.md
├── receipts
│   └── immutable
│       └── example-subject
│           ├── admissibility-decision-0000.yaml
│           ├── admissibility-decision-0001.yaml
│           ├── formula-eval-receipt-0001.yaml
│           ├── promotion-readiness-packet-0001.yaml
│           ├── reduction-decision-receipt-0000-promote.yaml
│           ├── reduction-decision-receipt-0001-include.yaml
│           └── reduction-decision-receipt-0001-promote.yaml
├── replay
│   └── manifests
│       └── example-subject
│           └── replay-0001.yaml
├── schemas
│   ├── PRIME_CANON_ADMISSIBILITY_DECISION_V1.schema.json
│   ├── PRIME_CANON_ADMISSIBILITY_PROFILE_V1.schema.json
│   ├── PRIME_CANON_ATTRIBUTE_DICTIONARY_V1.schema.json
│   ├── PRIME_CANON_CANDIDATE_CLAIM_V1.schema.json
│   ├── PRIME_CANON_CONTRADICTION_BUNDLE_V1.schema.json
│   ├── PRIME_CANON_CORPUS_INDEX_V1.schema.json
│   ├── PRIME_CANON_CURRENT_STATE_VIEW_V1.schema.json
│   ├── PRIME_CANON_EVIDENCE_LINK_V1.schema.json
│   ├── PRIME_CANON_FORMULA_EVAL_RECEIPT_V1.schema.json
│   ├── PRIME_CANON_FORMULA_PROFILE_V1.schema.json
│   ├── PRIME_CANON_JURISDICTION_BINDING_V1.schema.json
│   ├── PRIME_CANON_LANE_MANIFEST_V1.schema.json
│   ├── PRIME_CANON_NODE_V1.schema.json
│   ├── PRIME_CANON_PROMOTION_READINESS_PACKET_V1.schema.json
│   ├── PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1.schema.json
│   ├── PRIME_CANON_REPLAY_MANIFEST_V1.schema.json
│   ├── PRIME_CANON_REPO_MANIFEST_V1.schema.json
│   ├── PRIME_CANON_SOURCE_UNIT_V1.schema.json
│   ├── PRIME_CANON_SUPERSESSION_EDGE_V1.schema.json
│   └── prime-canon-bundle.schema.json
├── scripts
│   └── validate_pack.py
├── views
│   ├── current
│   │   └── example-subject.yaml
│   └── rendered
│       └── example-subject.md
├── FREEZE_ORDER.md
└── Makefile

```

## Minimal control-plane rules

1. `control/` changes land first and are review-heavy.
2. `receipts/immutable/` is append-only after merge.
3. `canon/nodes/` and `views/current/` change only through the promotion lane.
4. `views/rendered/` is never the authority surface.
5. `schemas/prime-canon-bundle.schema.json` is the single schema bundle used by the validator.
