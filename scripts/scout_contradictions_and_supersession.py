#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_contract import choose_enum, ensure_required_fields, validate_instance

CONTRADICTION_KIND = "PRIME_CANON_CONTRADICTION_BUNDLE_V1"
SUPERSESSION_KIND = "PRIME_CANON_SUPERSESSION_EDGE_V1"
RECEIPT_KIND = "PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def norm(s: str) -> str:
    return " ".join(s.lower().split())

def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def jaccard(a: str, b: str) -> float:
    ta = tokens(a)
    tb = tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def has_negation(s: str) -> bool:
    return bool(re.search(r"\b(no|not|never|cannot|can't|won't|isn't|aren't|don't|doesn't|without)\b", s.lower()))

def admissibility_passed(decision: dict) -> bool:
    return decision.get("spec", {}).get("pass_fail") == "pass"

def claim_scope_key(claim: dict) -> str:
    return str(claim["attributes"]["semantic"].get("scope", "")).strip().lower()

def claim_claim_type(claim: dict) -> str:
    return str(claim["spec"].get("claim_type", "")).strip().lower()

def build_contradiction(repo: Path, subject_slug: str, corpus_id: str, now: str, seq: int, left: dict, right: dict, source_refs: list[str], source_unit_refs: list[str]) -> dict:
    contradiction_id = f"pc.contradiction_bundle.{subject_slug}.{seq:04d}"
    rel_path = f"canon/contradictions/{subject_slug}/contradiction-scout-{seq:04d}.yaml"
    left_id = left["spec"]["claim_id"]
    right_id = right["spec"]["claim_id"]
    contradiction = {
        "kind": CONTRADICTION_KIND,
        "version": "v1",
        "metadata": {
            "object_id": contradiction_id,
            "display_name": f"{subject_slug} contradiction scout {seq:04d}",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:topology-scout@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "contradiction", "schema-driven"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": rel_path,
            },
            "lineage": {
                "source_refs": source_refs,
                "source_unit_refs": source_unit_refs,
                "reduction_path": ["topology_scout", "contradiction_scout"],
                "derivation_receipt_refs": [],
            },
            "evidence": {
                "burden_level": "medium",
                "sufficiency_status": "sufficient",
            },
            "governance": {
                "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                "approval_level": "peer",
                "actor_class": "compiler",
                "risk_tier": "medium",
                "promotion_tier": "candidate",
                "freeze_class": "mutable",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "topology-scout",
            },
            "relational": {
                "depends_on": [left_id, right_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "contradiction-supersession-scout",
                "repo_home": rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "contradiction",
            },
            "temporal": {
                "status_since": now,
                "replay_stability": "stable",
                "drift_sensitivity": "medium",
                "maturity": "working",
                "reduced_at": now,
            },
        },
        "spec": {
            "contradiction_id": contradiction_id,
            "object_refs": [left_id, right_id],
            "conflict_type": choose_enum(repo, CONTRADICTION_KIND, "conflict_type", "definition", "direct"),
            "severity": choose_enum(repo, CONTRADICTION_KIND, "severity", "medium", "low"),
            "conflict_scope": "normalized_claim_body",
            "open_questions": [
                f"Which claim should govern scope overlap between {left_id} and {right_id}?",
                "Is the apparent polarity mismatch substantive or only rhetorical?"
            ],
            "blocking": True,
            "adjudication_lane": "contradiction",
        },
    }
    ensure_required_fields(repo, CONTRADICTION_KIND, contradiction["spec"])
    validate_instance(repo, contradiction)
    return contradiction

def build_supersession(repo: Path, subject_slug: str, corpus_id: str, now: str, seq: int, prior: dict, successor: dict, source_refs: list[str], source_unit_refs: list[str], reason: str) -> dict:
    edge_id = f"pc.supersession_edge.{subject_slug}.{seq:04d}"
    rel_path = f"canon/supersession/{subject_slug}/edge-scout-{seq:04d}.yaml"
    edge = {
        "kind": SUPERSESSION_KIND,
        "version": "v1",
        "metadata": {
            "object_id": edge_id,
            "display_name": f"{subject_slug} supersession scout {seq:04d}",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:topology-scout@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "supersession", "schema-driven"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": rel_path,
            },
            "lineage": {
                "source_refs": source_refs,
                "source_unit_refs": source_unit_refs,
                "reduction_path": ["topology_scout", "supersession_scout"],
                "derivation_receipt_refs": [],
            },
            "evidence": {
                "burden_level": "medium",
                "sufficiency_status": "sufficient",
            },
            "governance": {
                "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                "approval_level": "peer",
                "actor_class": "compiler",
                "risk_tier": "medium",
                "promotion_tier": "candidate",
                "freeze_class": "mutable",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "topology-scout",
            },
            "relational": {
                "depends_on": [prior["spec"]["claim_id"], successor["spec"]["claim_id"]],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "contradiction-supersession-scout",
                "repo_home": rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "promotion-readiness",
            },
            "temporal": {
                "status_since": now,
                "replay_stability": "stable",
                "drift_sensitivity": "medium",
                "maturity": "working",
                "reduced_at": now,
            },
        },
        "spec": {
            "edge_id": edge_id,
            "prior_ref": prior["spec"]["claim_id"],
            "successor_ref": successor["spec"]["claim_id"],
            "supersession_type": choose_enum(repo, SUPERSESSION_KIND, "supersession_type", "refine", "replace"),
            "scope": choose_enum(repo, SUPERSESSION_KIND, "scope", "partial", "full"),
            "reason": reason,
            "inheritance_policy_ref": "pc.inheritance.default.v1",
            "effective_at": now,
            "unresolved_carryover_refs": [],
        },
    }
    ensure_required_fields(repo, SUPERSESSION_KIND, edge["spec"])
    validate_instance(repo, edge)
    return edge

def build_receipt(repo: Path, subject_slug: str, corpus_id: str, now: str, route_outcome: str, blocker_state: str, rationale: str, cited_receipt_refs: list[str], cited_object_refs: list[str]) -> dict:
    decision_receipt_id = f"pc.reduction_receipt.{subject_slug}.topology-scout"
    rel_path = f"receipts/immutable/{subject_slug}/topology-scout-summary.yaml"
    receipt = {
        "kind": RECEIPT_KIND,
        "version": "v1",
        "metadata": {
            "object_id": decision_receipt_id,
            "display_name": f"{subject_slug} topology scout summary",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:topology-scout@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "topology-scout", "schema-driven"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": rel_path,
            },
            "lineage": {
                "source_refs": [],
                "source_unit_refs": [],
                "reduction_path": ["topology_scout"],
                "derivation_receipt_refs": cited_receipt_refs,
            },
            "evidence": {
                "burden_level": "medium",
                "sufficiency_status": "sufficient",
            },
            "governance": {
                "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                "approval_level": "peer",
                "actor_class": "compiler",
                "risk_tier": "medium",
                "promotion_tier": "candidate",
                "freeze_class": "reviewed",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "topology-scout",
            },
            "relational": {
                "depends_on": cited_object_refs,
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "contradiction-supersession-scout",
                "repo_home": rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "promotion-readiness" if route_outcome == "promotion_lane" else "contradiction",
            },
            "temporal": {
                "status_since": now,
                "replay_stability": "stable",
                "drift_sensitivity": "medium",
                "maturity": "working",
                "reduced_at": now,
            },
        },
        "spec": {
            "decision_receipt_id": decision_receipt_id,
            "target_ref": corpus_id,
            "decision_type": choose_enum(repo, RECEIPT_KIND, "decision_type", "defer", "include"),
            "deciding_surface": choose_enum(repo, RECEIPT_KIND, "deciding_surface", "compiler", "human"),
            "rationale": rationale,
            "cited_receipt_refs": cited_receipt_refs,
            "cited_object_refs": cited_object_refs,
            "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
            "reviewer_refs": [],
            "blocker_state": choose_enum(repo, RECEIPT_KIND, "blocker_state", blocker_state, "none"),
            "route_outcome": choose_enum(repo, RECEIPT_KIND, "route_outcome", route_outcome, "deferred"),
        },
    }
    ensure_required_fields(repo, RECEIPT_KIND, receipt["spec"])
    validate_instance(repo, receipt)
    return receipt

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    claim_dir = repo / "canon" / "candidate_claims" / subject_slug
    admiss_dir = repo / "receipts" / "immutable" / subject_slug
    contradiction_dir = repo / "canon" / "contradictions" / subject_slug
    supersession_dir = repo / "canon" / "supersession" / subject_slug
    receipt_dir = repo / "receipts" / "immutable" / subject_slug
    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"

    if not claim_dir.exists():
        raise SystemExit(f"missing candidate claim dir: {claim_dir}")
    if not corpus_index_path.exists():
        raise SystemExit(f"missing corpus index: {corpus_index_path}")

    contradiction_dir.mkdir(parents=True, exist_ok=True)
    supersession_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    claim_files = sorted(p for p in claim_dir.glob("claim-*.yaml") if p.is_file())
    admiss_files = sorted(p for p in admiss_dir.glob("admissibility-*.yaml") if p.is_file())

    if not claim_files:
        raise SystemExit(f"no candidate claim files found in {claim_dir}")
    if not admiss_files:
        raise SystemExit(f"no admissibility decision files found in {admiss_dir}")

    corpus = yaml.safe_load(corpus_index_path.read_text(encoding="utf-8"))
    corpus_id = corpus["spec"]["corpus_id"]
    now = utc_now()

    admissibility_by_claim = {}
    cited_receipt_refs = []
    for path in admiss_files:
        decision = yaml.safe_load(path.read_text(encoding="utf-8"))
        claim_ref = decision["spec"]["target_claim_ref"]
        admissibility_by_claim[claim_ref] = decision
        cited_receipt_refs.append(decision["metadata"]["object_id"])

    claims = []
    for path in claim_files:
        claim = yaml.safe_load(path.read_text(encoding="utf-8"))
        if admissibility_passed(admissibility_by_claim.get(claim["spec"]["claim_id"], {})):
            claims.append(claim)

    contradiction_refs = []
    supersession_refs = []
    contradiction_seq = 1
    supersession_seq = 1
    seen_pairs = set()

    for i in range(len(claims)):
        left = claims[i]
        left_text = left["spec"]["normalized_claim_body"]
        left_type = claim_claim_type(left)
        for j in range(i + 1, len(claims)):
            right = claims[j]
            right_text = right["spec"]["normalized_claim_body"]
            right_type = claim_claim_type(right)
            pair_key = tuple(sorted([left["spec"]["claim_id"], right["spec"]["claim_id"]]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            overlap = jaccard(left_text, right_text)
            source_refs = sorted(set(left["attributes"]["lineage"].get("source_refs", []) + right["attributes"]["lineage"].get("source_refs", [])))
            source_unit_refs = sorted(set(left["attributes"]["lineage"].get("source_unit_refs", []) + right["attributes"]["lineage"].get("source_unit_refs", [])))

            if overlap >= 0.60 and has_negation(left_text) != has_negation(right_text):
                contradiction = build_contradiction(repo, subject_slug, corpus_id, now, contradiction_seq, left, right, source_refs, source_unit_refs)
                out = repo / contradiction["attributes"]["identity"]["canonical_home"]
                out.write_text(yaml.safe_dump(contradiction, sort_keys=False), encoding="utf-8")
                contradiction_refs.append(contradiction["metadata"]["object_id"])
                contradiction_seq += 1
                continue

            same_scope = claim_scope_key(left) == claim_scope_key(right)
            neither_question = left_type != "question" and right_type != "question"
            left_norm = norm(left_text)
            right_norm = norm(right_text)

            if same_scope and neither_question:
                if left_norm != right_norm and left_norm in right_norm and len(right_norm) - len(left_norm) >= 24:
                    edge = build_supersession(repo, subject_slug, corpus_id, now, supersession_seq, left, right, source_refs, source_unit_refs, "successor claim strictly contains prior claim text and adds more specific scope")
                    out = repo / edge["attributes"]["identity"]["canonical_home"]
                    out.write_text(yaml.safe_dump(edge, sort_keys=False), encoding="utf-8")
                    supersession_refs.append(edge["metadata"]["object_id"])
                    supersession_seq += 1
                    continue
                if left_norm != right_norm and right_norm in left_norm and len(left_norm) - len(right_norm) >= 24:
                    edge = build_supersession(repo, subject_slug, corpus_id, now, supersession_seq, right, left, source_refs, source_unit_refs, "successor claim strictly contains prior claim text and adds more specific scope")
                    out = repo / edge["attributes"]["identity"]["canonical_home"]
                    out.write_text(yaml.safe_dump(edge, sort_keys=False), encoding="utf-8")
                    supersession_refs.append(edge["metadata"]["object_id"])
                    supersession_seq += 1
                    continue

    cited_object_refs = [c["spec"]["claim_id"] for c in claims] + contradiction_refs + supersession_refs

    if contradiction_refs:
        route_outcome = "contradiction_lane"
        blocker_state = "present_unresolved"
        rationale = f"topology scout found {len(contradiction_refs)} contradiction bundle(s) and {len(supersession_refs)} supersession edge(s); unresolved blockers remain"
        route_destination = "contradiction"
    else:
        route_outcome = "promotion_lane"
        blocker_state = "none"
        rationale = f"topology scout found {len(contradiction_refs)} contradiction bundle(s) and {len(supersession_refs)} supersession edge(s); corpus can advance to promotion readiness"
        route_destination = "promotion-readiness"

    receipt = build_receipt(repo, subject_slug, corpus_id, now, route_outcome, blocker_state, rationale, cited_receipt_refs, cited_object_refs)
    (repo / receipt["attributes"]["identity"]["canonical_home"]).write_text(yaml.safe_dump(receipt, sort_keys=False), encoding="utf-8")

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = route_destination
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

    print(f"generated {len(contradiction_refs)} contradiction bundles for {subject_slug}")
    for ref in contradiction_refs:
        print(ref)
    print(f"generated {len(supersession_refs)} supersession edges for {subject_slug}")
    for ref in supersession_refs:
        print(ref)
    print(receipt["metadata"]["object_id"])

if __name__ == "__main__":
    main()
