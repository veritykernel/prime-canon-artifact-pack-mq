#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_contract import choose_enum, ensure_required_fields, validate_instance

PACKET_KIND = "PRIME_CANON_PROMOTION_READINESS_PACKET_V1"
MANIFEST_KIND = "PRIME_CANON_REPLAY_MANIFEST_V1"
RECEIPT_KIND = "PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def blast_radius_for(repo: Path, target_count: int) -> str:
    if target_count <= 5:
        preferred = "low"
    elif target_count <= 20:
        preferred = "medium"
    elif target_count <= 50:
        preferred = "high"
    else:
        preferred = "critical"
    return choose_enum(repo, PACKET_KIND, "blast_radius", preferred, "medium")

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"
    claim_dir = repo / "canon" / "candidate_claims" / subject_slug
    evidence_dir = repo / "canon" / "evidence_links" / subject_slug
    contradiction_dir = repo / "canon" / "contradictions" / subject_slug
    supersession_dir = repo / "canon" / "supersession" / subject_slug
    receipt_dir = repo / "receipts" / "immutable" / subject_slug
    replay_dir = repo / "replay" / "manifests" / subject_slug

    if not corpus_index_path.exists():
        raise SystemExit(f"missing corpus index: {corpus_index_path}")
    if not claim_dir.exists():
        raise SystemExit(f"missing candidate claim dir: {claim_dir}")
    if not evidence_dir.exists():
        raise SystemExit(f"missing evidence link dir: {evidence_dir}")
    if not receipt_dir.exists():
        raise SystemExit(f"missing receipt dir: {receipt_dir}")

    replay_dir.mkdir(parents=True, exist_ok=True)

    claim_files = sorted(p for p in claim_dir.glob("claim-*.yaml") if p.is_file())
    evidence_files = sorted(p for p in evidence_dir.glob("link-*.yaml") if p.is_file())
    admissibility_files = sorted(p for p in receipt_dir.glob("admissibility-*.yaml") if p.is_file())
    contradiction_files = sorted(p for p in contradiction_dir.glob("contradiction-*.yaml") if p.is_file())
    supersession_files = sorted(p for p in supersession_dir.glob("edge-*.yaml") if p.is_file())
    topology_receipt_path = receipt_dir / "topology-scout-summary.yaml"

    if not claim_files:
        raise SystemExit(f"no candidate claims found in {claim_dir}")
    if not evidence_files:
        raise SystemExit(f"no evidence links found in {evidence_dir}")
    if not admissibility_files:
        raise SystemExit(f"no admissibility decisions found in {receipt_dir}")
    if not topology_receipt_path.exists():
        raise SystemExit(f"missing topology summary receipt: {topology_receipt_path}")

    corpus = yaml.safe_load(corpus_index_path.read_text(encoding="utf-8"))
    corpus_id = corpus["spec"]["corpus_id"]
    now = utc_now()

    admissibility_by_claim = {}
    admissibility_receipt_ids = []
    admissibility_paths_by_id = {}

    for path in admissibility_files:
        decision = yaml.safe_load(path.read_text(encoding="utf-8"))
        claim_ref = decision["spec"]["target_claim_ref"]
        decision_id = decision["metadata"]["object_id"]
        admissibility_by_claim[claim_ref] = decision
        admissibility_receipt_ids.append(decision_id)
        admissibility_paths_by_id[decision_id] = path

    target_claims = []
    target_claim_ids = []
    claim_paths_by_id = {}
    for path in claim_files:
        claim = yaml.safe_load(path.read_text(encoding="utf-8"))
        claim_id = claim["spec"]["claim_id"]
        claim_paths_by_id[claim_id] = path
        decision = admissibility_by_claim.get(claim_id)
        if decision and decision["spec"]["pass_fail"] == "pass":
            target_claims.append(claim)
            target_claim_ids.append(claim_id)

    evidence_link_ids = []
    evidence_paths_by_id = {}
    for path in evidence_files:
        link = yaml.safe_load(path.read_text(encoding="utf-8"))
        link_id = link["metadata"]["object_id"]
        evidence_link_ids.append(link_id)
        evidence_paths_by_id[link_id] = path

    contradiction_ids = []
    for path in contradiction_files:
        obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        contradiction_ids.append(obj["metadata"]["object_id"])

    supersession_ids = []
    for path in supersession_files:
        obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        supersession_ids.append(obj["metadata"]["object_id"])

    topology_receipt = yaml.safe_load(topology_receipt_path.read_text(encoding="utf-8"))
    topology_receipt_id = topology_receipt["metadata"]["object_id"]
    topology_blocker_state = topology_receipt["spec"]["blocker_state"]

    required_gates = [
        "candidate_claims_present",
        "evidence_links_present",
        "admissibility_all_pass",
        "topology_summary_present",
        "topology_blockers_clear",
        "replay_manifest_built",
    ]

    gate_results = []

    claims_present = len(target_claim_ids) > 0
    gate_results.append({
        "gate": "candidate_claims_present",
        "status": "pass" if claims_present else "fail",
        "evidence": target_claim_ids,
    })

    links_present = len(evidence_link_ids) >= len(target_claim_ids) and len(evidence_link_ids) > 0
    gate_results.append({
        "gate": "evidence_links_present",
        "status": "pass" if links_present else "fail",
        "evidence": evidence_link_ids,
    })

    all_admissible = claims_present and len(target_claim_ids) == len(claim_files) and all(
        admissibility_by_claim[c["spec"]["claim_id"]]["spec"]["pass_fail"] == "pass"
        for c in target_claims
    )
    gate_results.append({
        "gate": "admissibility_all_pass",
        "status": "pass" if all_admissible else "fail",
        "evidence": admissibility_receipt_ids,
    })

    topology_present = True
    gate_results.append({
        "gate": "topology_summary_present",
        "status": "pass" if topology_present else "missing",
        "evidence": [topology_receipt_id],
    })

    topology_clear = topology_blocker_state == "none" and len(contradiction_ids) == 0
    gate_results.append({
        "gate": "topology_blockers_clear",
        "status": "pass" if topology_clear else "blocked",
        "evidence": [topology_receipt_id] + contradiction_ids,
    })

    manifest_id = f"pc.replay_manifest.{subject_slug}.promotion-readiness"
    manifest_rel_path = f"replay/manifests/{subject_slug}/promotion-readiness-replay.yaml"
    packet_id = f"pc.promotion_readiness.{subject_slug}.packet"
    packet_rel_path = f"receipts/immutable/{subject_slug}/promotion-readiness-packet.yaml"
    summary_receipt_id = f"pc.reduction_receipt.{subject_slug}.promotion-readiness"
    summary_rel_path = f"receipts/immutable/{subject_slug}/promotion-readiness-summary.yaml"

    object_ref_paths = {}
    for claim_id in target_claim_ids:
        object_ref_paths[claim_id] = claim_paths_by_id[claim_id]
    for link_id, path in evidence_paths_by_id.items():
        object_ref_paths[link_id] = path
    for receipt_id, path in admissibility_paths_by_id.items():
        object_ref_paths[receipt_id] = path
    object_ref_paths[topology_receipt_id] = topology_receipt_path

    input_hashes = []
    for object_ref in sorted(object_ref_paths):
        input_hashes.append({
            "object_ref": object_ref,
            "sha256": sha256_file(object_ref_paths[object_ref]),
        })

    replay_manifest = {
        "kind": MANIFEST_KIND,
        "version": "v1",
        "metadata": {
            "object_id": manifest_id,
            "display_name": f"{subject_slug} promotion readiness replay manifest",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:promotion-readiness-builder@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "replay-manifest", "promotion-readiness"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": manifest_rel_path,
            },
            "lineage": {
                "source_refs": [],
                "source_unit_refs": [],
                "reduction_path": ["promotion_readiness", "replay_manifest"],
                "derivation_receipt_refs": [topology_receipt_id] + admissibility_receipt_ids,
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
                "scope": "promotion-readiness",
            },
            "relational": {
                "depends_on": sorted(object_ref_paths.keys()),
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "promotion-readiness",
                "repo_home": manifest_rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "promotion_lane",
            },
            "temporal": {
                "status_since": now,
                "replay_stability": "stable",
                "drift_sensitivity": "low",
                "maturity": "working",
                "reduced_at": now,
            },
        },
        "spec": {
            "manifest_id": manifest_id,
            "scope_ref": corpus_id,
            "object_refs": sorted(object_ref_paths.keys()),
            "profile_refs": [
                "pc.admissibility.default.v1",
                "pc.promotion.default.v1",
            ],
            "compiler_refs": [
                "compiler:promotion-readiness-builder@1.0.0",
                "script:schema_contract.py",
            ],
            "input_hashes": input_hashes,
            "expected_output_refs": [packet_id, summary_receipt_id],
            "environment_assumptions": [
                "schema bundle frozen",
                "control surfaces frozen",
                "local repo state validated",
            ],
            "replay_class": choose_enum(repo, MANIFEST_KIND, "replay_class", "deterministic", "local"),
            "generated_from_ref": topology_receipt_id,
        },
    }

    ensure_required_fields(repo, MANIFEST_KIND, replay_manifest["spec"])
    validate_instance(repo, replay_manifest)

    gate_results.append({
        "gate": "replay_manifest_built",
        "status": "pass",
        "evidence": [manifest_id],
    })

    blockers = []
    for item in gate_results:
        if item["status"] in {"fail", "blocked", "missing"}:
            blockers.append(item["gate"])
    if topology_blocker_state != "none" and "topology_blockers_clear" not in blockers:
        blockers.append("topology_blockers_clear")

    ready = len(blockers) == 0 and len(target_claim_ids) > 0
    blast_radius = blast_radius_for(repo, len(target_claim_ids))

    promotion_packet = {
        "kind": PACKET_KIND,
        "version": "v1",
        "metadata": {
            "object_id": packet_id,
            "display_name": f"{subject_slug} promotion readiness packet",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:promotion-readiness-builder@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "promotion-readiness", "schema-driven"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": packet_rel_path,
            },
            "lineage": {
                "source_refs": [],
                "source_unit_refs": [],
                "reduction_path": ["promotion_readiness"],
                "derivation_receipt_refs": [topology_receipt_id] + admissibility_receipt_ids + [manifest_id],
            },
            "evidence": {
                "burden_level": "medium",
                "sufficiency_status": "sufficient" if ready else "insufficient",
            },
            "governance": {
                "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                "approval_level": "peer",
                "actor_class": "compiler",
                "risk_tier": blast_radius,
                "promotion_tier": "candidate",
                "freeze_class": "reviewed",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "promotion-readiness",
            },
            "relational": {
                "depends_on": target_claim_ids + evidence_link_ids + admissibility_receipt_ids + [topology_receipt_id, manifest_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "promotion-readiness",
                "repo_home": packet_rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "promotion_lane" if ready else "deferred",
            },
            "temporal": {
                "status_since": now,
                "replay_stability": "stable",
                "drift_sensitivity": "low",
                "maturity": "working",
                "reduced_at": now,
            },
        },
        "spec": {
            "packet_id": packet_id,
            "target_refs": target_claim_ids,
            "required_gates": required_gates,
            "gate_results": gate_results,
            "blockers": blockers,
            "required_reviewer_classes": ["human-reviewer"],
            "blast_radius": blast_radius,
            "replay_manifest_ref": manifest_id,
            "ready": ready,
        },
    }

    ensure_required_fields(repo, PACKET_KIND, promotion_packet["spec"])
    validate_instance(repo, promotion_packet)

    if ready:
        decision_type = choose_enum(repo, RECEIPT_KIND, "decision_type", "defer", "include")
        blocker_state = choose_enum(repo, RECEIPT_KIND, "blocker_state", "none", "present_resolved")
        route_outcome = choose_enum(repo, RECEIPT_KIND, "route_outcome", "promotion_lane", "deferred")
        rationale = f"promotion readiness passed for {len(target_claim_ids)} admissible claim(s); topology blockers clear; replay manifest pinned"
    else:
        decision_type = choose_enum(repo, RECEIPT_KIND, "decision_type", "defer", "reject")
        blocker_state = choose_enum(repo, RECEIPT_KIND, "blocker_state", "present_unresolved", "present_resolved")
        route_outcome = choose_enum(repo, RECEIPT_KIND, "route_outcome", "deferred", "candidate_pool")
        rationale = f"promotion readiness blocked by gates: {', '.join(blockers)}"

    summary_receipt = {
        "kind": RECEIPT_KIND,
        "version": "v1",
        "metadata": {
            "object_id": summary_receipt_id,
            "display_name": f"{subject_slug} promotion readiness summary",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:promotion-readiness-builder@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "promotion-readiness", "summary"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": summary_rel_path,
            },
            "lineage": {
                "source_refs": [],
                "source_unit_refs": [],
                "reduction_path": ["promotion_readiness", "summary_receipt"],
                "derivation_receipt_refs": [topology_receipt_id] + admissibility_receipt_ids + [manifest_id, packet_id],
            },
            "evidence": {
                "burden_level": "medium",
                "sufficiency_status": "sufficient" if ready else "insufficient",
            },
            "governance": {
                "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                "approval_level": "peer",
                "actor_class": "compiler",
                "risk_tier": blast_radius,
                "promotion_tier": "candidate",
                "freeze_class": "reviewed",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "promotion-readiness",
            },
            "relational": {
                "depends_on": target_claim_ids + evidence_link_ids + [packet_id, manifest_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "promotion-readiness",
                "repo_home": summary_rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "promotion_lane" if ready else "deferred",
            },
            "temporal": {
                "status_since": now,
                "replay_stability": "stable",
                "drift_sensitivity": "low",
                "maturity": "working",
                "reduced_at": now,
            },
        },
        "spec": {
            "decision_receipt_id": summary_receipt_id,
            "target_ref": packet_id,
            "decision_type": decision_type,
            "deciding_surface": choose_enum(repo, RECEIPT_KIND, "deciding_surface", "compiler", "ci"),
            "rationale": rationale,
            "cited_receipt_refs": [topology_receipt_id] + admissibility_receipt_ids,
            "cited_object_refs": target_claim_ids + evidence_link_ids + [manifest_id, packet_id],
            "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
            "reviewer_refs": [],
            "blocker_state": blocker_state,
            "route_outcome": route_outcome,
        },
    }

    ensure_required_fields(repo, RECEIPT_KIND, summary_receipt["spec"])
    validate_instance(repo, summary_receipt)

    (repo / manifest_rel_path).write_text(yaml.safe_dump(replay_manifest, sort_keys=False), encoding="utf-8")
    (repo / packet_rel_path).write_text(yaml.safe_dump(promotion_packet, sort_keys=False), encoding="utf-8")
    (repo / summary_rel_path).write_text(yaml.safe_dump(summary_receipt, sort_keys=False), encoding="utf-8")

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = "promotion_lane" if ready else "deferred"
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

    print(manifest_id)
    print(packet_id)
    print(summary_receipt_id)
    print(f"ready={str(ready).lower()}")
    print(f"targets={len(target_claim_ids)}")
    print(f"blockers={len(blockers)}")

if __name__ == "__main__":
    main()
