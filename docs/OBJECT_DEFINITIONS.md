# Prime Canon Object Definitions

This pack freezes a single object envelope for all repo-native canon artifacts:

```yaml
kind: PRIME_CANON_<FAMILY>_V1
version: v1
metadata: {...}
attributes: {...}
spec: {...}
```

## Common envelope

- `metadata`: stable object identity, display name, timestamps, author, owners, tags.

- `attributes.identity`: `corpus_id`, `subject_slug`, `canonical_home`.

- `attributes.lineage`: `source_refs`, `source_unit_refs`, reduction path, derivation receipts.

- `attributes.evidence`: burden class, sufficiency status, replayability.

- `attributes.governance`: jurisdiction, approval level, actor class, risk tier, promotion tier, freeze class.

- `attributes.semantic`: domain, scope, type, dependency footprint, density, novelty.

- `attributes.relational`: contradiction, supersession, dependency, section, cluster edges.

- `attributes.operational`: lane, repo home, active state, mirror permissions, maintenance burden, next route.

- `attributes.temporal`: observed/reduced/status timestamps, replay stability, drift sensitivity, maturity.

## PRIME_CANON_REPO_MANIFEST_V1

Repository enrollment object for the prime canon control plane.

Required `spec` fields: `repo_id, repo_name, canon_enabled, enrolled_surfaces, default_formula_profile_ref, default_admissibility_profile_ref, jurisdiction_binding_refs, lane_manifest_refs, render_fail_closed, federation_mode, canonical_branches, protected_paths`.

Schema file: `schemas/PRIME_CANON_REPO_MANIFEST_V1.schema.json`.

## PRIME_CANON_ATTRIBUTE_DICTIONARY_V1

Attribute lattice definition for canon-bearing objects.

Required `spec` fields: `dictionary_id, bands`.

Schema file: `schemas/PRIME_CANON_ATTRIBUTE_DICTIONARY_V1.schema.json`.

## PRIME_CANON_FORMULA_PROFILE_V1

Versioned formula profile for scoring and gate evaluation.

Required `spec` fields: `profile_id, objective, measurements, composites, hard_gates, expiry_policy`.

Schema file: `schemas/PRIME_CANON_FORMULA_PROFILE_V1.schema.json`.

## PRIME_CANON_ADMISSIBILITY_PROFILE_V1

Admissibility burden profile used before canon promotion.

Required `spec` fields: `profile_id, burden_classes, override_policy, provisional_policy`.

Schema file: `schemas/PRIME_CANON_ADMISSIBILITY_PROFILE_V1.schema.json`.

## PRIME_CANON_JURISDICTION_BINDING_V1

Binding that constrains actor permissions by object family and lane.

Required `spec` fields: `binding_id, actor_class, actor_ref, object_family, allowed_actions, forbidden_actions, allowed_lanes, required_receipt_kinds, escalation_targets, review_burden, repo_boundary_behavior, risk_ceiling`.

Schema file: `schemas/PRIME_CANON_JURISDICTION_BINDING_V1.schema.json`.

## PRIME_CANON_LANE_MANIFEST_V1

Lane contract for repo-native canon operations.

Required `spec` fields: `lane_id, allowed_object_families, required_receipt_kinds, forbidden_actions, required_checks, mutation_paths, rollback_strategy, escalation_policy`.

Schema file: `schemas/PRIME_CANON_LANE_MANIFEST_V1.schema.json`.

## PRIME_CANON_CORPUS_INDEX_V1

Subject-scoped intake index for a canon run.

Required `spec` fields: `corpus_id, subject_slug, source_refs, source_ordering, intake_scope, source_count, compiler_version, intake_policy_ref, status`.

Schema file: `schemas/PRIME_CANON_CORPUS_INDEX_V1.schema.json`.

## PRIME_CANON_SOURCE_UNIT_V1

Normalized atomic source segment used as claim extraction substrate.

Required `spec` fields: `source_unit_id, corpus_id, source_ref, span_ref, normalized_text, extraction_method, source_kind, checksum`.

Schema file: `schemas/PRIME_CANON_SOURCE_UNIT_V1.schema.json`.

## PRIME_CANON_CANDIDATE_CLAIM_V1

Candidate canon claim extracted from normalized source units.

Required `spec` fields: `claim_id, corpus_id, canonical_phrase, normalized_claim_body, claim_type, source_unit_refs, claim_scope, claim_domain, extraction_confidence, candidate_state, merge_key`.

Schema file: `schemas/PRIME_CANON_CANDIDATE_CLAIM_V1.schema.json`.

## PRIME_CANON_EVIDENCE_LINK_V1

Structured link between a candidate claim and supporting or contradicting evidence.

Required `spec` fields: `link_id, claim_ref, evidence_ref, evidence_class, support_type, support_strength, source_trust_class, admissibility_weight, replayable`.

Schema file: `schemas/PRIME_CANON_EVIDENCE_LINK_V1.schema.json`.

## PRIME_CANON_ADMISSIBILITY_DECISION_V1

Admissibility gate output for a candidate claim.

Required `spec` fields: `decision_id, target_claim_ref, profile_ref, pass_fail, met_burdens, unmet_burdens, reasons, deciding_surface, override_used`.

Schema file: `schemas/PRIME_CANON_ADMISSIBILITY_DECISION_V1.schema.json`.

## PRIME_CANON_FORMULA_EVAL_RECEIPT_V1

Replayable formula output receipt tied to a versioned profile.

Required `spec` fields: `receipt_id, target_ref, formula_profile_ref, input_snapshot, output_metrics, score_decomposition, replay_hash`.

Schema file: `schemas/PRIME_CANON_FORMULA_EVAL_RECEIPT_V1.schema.json`.

## PRIME_CANON_CONTRADICTION_BUNDLE_V1

Durable contradiction state between canon-relevant objects.

Required `spec` fields: `contradiction_id, object_refs, conflict_type, severity, conflict_scope, open_questions, blocking, adjudication_lane`.

Schema file: `schemas/PRIME_CANON_CONTRADICTION_BUNDLE_V1.schema.json`.

## PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1

Immutable receipt for reduction, rejection, promotion, or routing decisions.

Required `spec` fields: `decision_receipt_id, target_ref, decision_type, deciding_surface, rationale, cited_receipt_refs, cited_object_refs, jurisdiction_ref, reviewer_refs, blocker_state, route_outcome`.

Schema file: `schemas/PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1.schema.json`.

## PRIME_CANON_SUPERSESSION_EDGE_V1

Explicit supersession relationship between canon-bearing objects.

Required `spec` fields: `edge_id, prior_ref, successor_ref, supersession_type, scope, reason, inheritance_policy_ref, effective_at, unresolved_carryover_refs`.

Schema file: `schemas/PRIME_CANON_SUPERSESSION_EDGE_V1.schema.json`.

## PRIME_CANON_NODE_V1

Promotable canon-bearing node derived from an adjudicated claim.

Required `spec` fields: `canon_node_id, originating_claim_ref, canonical_body, state, section_memberships, active_projection_flags, confidence, promotion_receipt_ref`.

Schema file: `schemas/PRIME_CANON_NODE_V1.schema.json`.

## PRIME_CANON_PROMOTION_READINESS_PACKET_V1

Aggregated promotion readiness state for one or more canon targets.

Required `spec` fields: `packet_id, target_refs, required_gates, gate_results, blockers, required_reviewer_classes, blast_radius, replay_manifest_ref, ready`.

Schema file: `schemas/PRIME_CANON_PROMOTION_READINESS_PACKET_V1.schema.json`.

## PRIME_CANON_REPLAY_MANIFEST_V1

Pinned input/output manifest for deterministic replay.

Required `spec` fields: `manifest_id, scope_ref, object_refs, profile_refs, compiler_refs, input_hashes, expected_output_refs, environment_assumptions, replay_class, generated_from_ref`.

Schema file: `schemas/PRIME_CANON_REPLAY_MANIFEST_V1.schema.json`.

## PRIME_CANON_CURRENT_STATE_VIEW_V1

Derived current-state read model for active canon objects.

Required `spec` fields: `view_id, scope_ref, active_node_refs, active_edge_refs, active_contradiction_refs, unresolved_blocker_refs, view_hash, derivation_receipt_refs, generated_at`.

Schema file: `schemas/PRIME_CANON_CURRENT_STATE_VIEW_V1.schema.json`.
