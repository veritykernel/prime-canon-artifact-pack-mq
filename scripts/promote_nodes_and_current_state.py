#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import fcntl
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_contract import choose_enum, ensure_required_fields, validate_instance
from promotion_preflight import PromotionRejected, preflight

NODE_KIND = "PRIME_CANON_NODE_V1"
VIEW_KIND = "PRIME_CANON_CURRENT_STATE_VIEW_V1"
RECEIPT_KIND = "PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def claim_seq_from_path(path: Path) -> str:
    return path.stem.replace("claim-", "")

def write_new(repo: Path, path: Path, obj: dict) -> None:
    """Never overwrite a prior canon object or follow an output symlink."""
    if not path.parent.resolve().is_relative_to(repo):
        raise PromotionRejected(f"output path escapes repository: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(yaml.safe_dump(obj, sort_keys=False))

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"
    claim_dir = repo / "canon" / "candidate_claims" / subject_slug
    evidence_dir = repo / "canon" / "evidence_links" / subject_slug
    node_dir = repo / "canon" / "nodes" / subject_slug
    receipt_dir = repo / "receipts" / "immutable" / subject_slug
    current_view_path = repo / "views" / "current" / f"{subject_slug}.yaml"
    packet_path = receipt_dir / "promotion-readiness-packet.yaml"
    readiness_summary_path = receipt_dir / "promotion-readiness-summary.yaml"
    replay_manifest_path = repo / "replay" / "manifests" / subject_slug / "promotion-readiness-replay.yaml"

    try:
        frozen = preflight(
            repo, subject_slug,
            approval_path=Path(os.environ["PRIME_CANON_APPROVAL"]) if os.environ.get("PRIME_CANON_APPROVAL") else None,
            signature_path=Path(os.environ["PRIME_CANON_APPROVAL_SIGNATURE"]) if os.environ.get("PRIME_CANON_APPROVAL_SIGNATURE") else None,
            signers_path=Path(os.environ["PRIME_CANON_ALLOWED_SIGNERS"]) if os.environ.get("PRIME_CANON_ALLOWED_SIGNERS") else None,
        )
    except PromotionRejected as exc:
        raise SystemExit(f"promotion rejected: {exc}") from exc

    corpus = frozen["corpus"]
    packet = frozen["packet"]
    readiness_summary = frozen["summary"]
    replay_manifest = frozen["manifest"]
    reviewer = frozen["reviewer"]
    approval_hash = frozen["approval_sha256"]

    corpus_id = corpus["spec"]["corpus_id"]
    now = utc_now()
    target_claim_ids = list(packet["spec"]["target_refs"])
    packet_id = packet["metadata"]["object_id"]
    readiness_summary_id = readiness_summary["metadata"]["object_id"]
    replay_manifest_id = replay_manifest["metadata"]["object_id"]

    claim_paths_by_id = {key: value[2] for key, value in frozen["claims"].items()}
    evidence_links_by_claim = frozen["links"]

    missing_claims = [claim_id for claim_id in target_claim_ids if claim_id not in claim_paths_by_id]
    if missing_claims:
        raise SystemExit(f"missing claim files for target refs: {missing_claims}")

    missing_links = [claim_id for claim_id in target_claim_ids if claim_id not in evidence_links_by_claim]
    if missing_links:
        raise SystemExit(f"missing evidence links for target refs: {missing_links}")

    # Check every output before the first write. Immutable receipts and nodes
    # must never be silently replaced by a rerun of the compiler.
    outputs = [current_view_path, receipt_dir / "promotion-lane-summary.yaml"]
    for claim_id in target_claim_ids:
        seq = claim_seq_from_path(claim_paths_by_id[claim_id])
        outputs.extend((node_dir / f"node-{seq}.yaml", receipt_dir / f"promotion-node-{seq}.yaml"))
    if any(path.exists() or path.is_symlink() for path in outputs):
        raise SystemExit("promotion outputs already exist; reconcile the prior effect before retrying")
    corpus_fd = os.open(corpus_index_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    corpus_stream = os.fdopen(corpus_fd, "r+b")
    fcntl.flock(corpus_stream.fileno(), fcntl.LOCK_EX)
    if hashlib.sha256(corpus_stream.read(2 * 1024 * 1024 + 1)).hexdigest() != frozen["corpus_sha256"]:
        corpus_stream.close()
        raise SystemExit("corpus changed after signed preflight; no promotion outputs written")
    node_dir.mkdir(parents=True, exist_ok=True)
    current_view_path.parent.mkdir(parents=True, exist_ok=True)

    node_ids = []
    node_receipt_ids = []
    all_source_refs = []
    all_source_unit_refs = []

    for claim_id in target_claim_ids:
        claim_path = claim_paths_by_id[claim_id]
        claim = frozen["claims"][claim_id][0]
        seq = claim_seq_from_path(claim_path)
        link = evidence_links_by_claim[claim_id]
        link_id = link["metadata"]["object_id"]

        source_refs = list(claim["attributes"]["lineage"].get("source_refs", []))
        source_unit_refs = list(claim["attributes"]["lineage"].get("source_unit_refs", []))
        all_source_refs.extend(source_refs)
        all_source_unit_refs.extend(source_unit_refs)

        node_id = f"pc.canon_node.{subject_slug}.{seq}"
        node_rel_path = f"canon/nodes/{subject_slug}/node-{seq}.yaml"
        receipt_id = f"pc.reduction_receipt.{subject_slug}.promote-{seq}"
        receipt_rel_path = f"receipts/immutable/{subject_slug}/promotion-node-{seq}.yaml"

        canonical_body = claim["spec"]["normalized_claim_body"]
        confidence = float(claim["spec"].get("extraction_confidence", 0.85))
        state = choose_enum(repo, NODE_KIND, "state", "promoted", "provisional")

        receipt = {
            "kind": RECEIPT_KIND,
            "version": "v1",
            "metadata": {
                "object_id": receipt_id,
                "display_name": f"{subject_slug} promotion receipt {seq}",
                "created_at": now,
                "updated_at": now,
                "created_by": "compiler:promotion-lane-builder@1.0.0",
                "owners": ["team:prime-canon"],
                "tags": ["prime-canon", subject_slug, "promotion", "node"],
            },
            "attributes": {
                "identity": {
                    "corpus_id": corpus_id,
                    "subject_slug": subject_slug,
                    "canonical_home": receipt_rel_path,
                },
                "lineage": {
                    "source_refs": source_refs,
                    "source_unit_refs": source_unit_refs,
                    "reduction_path": list(claim["attributes"]["lineage"].get("reduction_path", [])) + ["promotion_lane"],
                    "derivation_receipt_refs": [packet_id, readiness_summary_id, replay_manifest_id, link_id],
                },
                "evidence": {
                    "evidence_class": claim["attributes"]["evidence"].get("evidence_class", "direct_quote"),
                    "evidence_ref_count": int(claim["attributes"]["evidence"].get("evidence_ref_count", 1)),
                    "burden_level": claim["attributes"]["evidence"].get("burden_level", "medium"),
                    "sufficiency_status": "sufficient",
                    "replayability_class": claim["attributes"]["evidence"].get("replayability_class", "high"),
                },
                "governance": {
                    "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                    "approval_level": "peer",
                    "actor_class": "compiler",
                    "risk_tier": claim["attributes"]["governance"].get("risk_tier", "medium"),
                    "promotion_tier": "promoted",
                    "freeze_class": "reviewed",
                },
                "semantic": {
                    "domain": claim["attributes"]["semantic"].get("domain", "prime-canon"),
                    "scope": "promotion-lane",
                    "dependency_footprint": [],
                    "semantic_density": float(claim["attributes"]["semantic"].get("semantic_density", 0.80)),
                    "novelty_state": claim["attributes"]["semantic"].get("novelty_state", "unknown"),
                },
                "relational": {
                    "contradiction_refs": [],
                    "supersedes": [],
                    "superseded_by": [],
                    "depends_on": [claim_id, packet_id, link_id],
                    "section_refs": [],
                    "cluster_refs": [],
                },
                "operational": {
                    "lane_ref": "promotion-lane",
                    "repo_home": receipt_rel_path,
                    "active_state": "active",
                    "mirror_permissions": "local_only",
                    "maintenance_burden": claim["attributes"]["operational"].get("maintenance_burden", "low"),
                    "route_destination": "current-state-view",
                },
                "temporal": {
                    "observed_at": claim["attributes"]["temporal"].get("observed_at"),
                    "reduced_at": now,
                    "status_since": now,
                    "replay_stability": claim["attributes"]["temporal"].get("replay_stability", "stable"),
                    "drift_sensitivity": claim["attributes"]["temporal"].get("drift_sensitivity", "low"),
                    "maturity": "working",
                },
            },
            "spec": {
                "decision_receipt_id": receipt_id,
                "target_ref": claim_id,
                "decision_type": choose_enum(repo, RECEIPT_KIND, "decision_type", "promote", "include"),
                "deciding_surface": choose_enum(repo, RECEIPT_KIND, "deciding_surface", "compiler", "ci"),
                "rationale": f"claim {claim_id} promoted into canon node {node_id} from ready promotion packet {packet_id}; signed human approval sha256:{approval_hash}",
                "cited_receipt_refs": [packet_id, readiness_summary_id],
                "cited_object_refs": [claim_id, link_id, replay_manifest_id],
                "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                "reviewer_refs": [reviewer],
                "blocker_state": choose_enum(repo, RECEIPT_KIND, "blocker_state", "none", "present_resolved"),
                "route_outcome": choose_enum(repo, RECEIPT_KIND, "route_outcome", "promotion_lane", "candidate_pool"),
            },
        }

        ensure_required_fields(repo, RECEIPT_KIND, receipt["spec"])
        validate_instance(repo, receipt)

        node = {
            "kind": NODE_KIND,
            "version": "v1",
            "metadata": {
                "object_id": node_id,
                "display_name": f"{subject_slug} canon node {seq}",
                "created_at": now,
                "updated_at": now,
                "created_by": "compiler:promotion-lane-builder@1.0.0",
                "owners": ["team:prime-canon"],
                "tags": ["prime-canon", subject_slug, "canon-node", "promoted"],
            },
            "attributes": {
                "identity": {
                    "corpus_id": corpus_id,
                    "subject_slug": subject_slug,
                    "canonical_home": node_rel_path,
                },
                "lineage": {
                    "source_refs": source_refs,
                    "source_unit_refs": source_unit_refs,
                    "reduction_path": list(claim["attributes"]["lineage"].get("reduction_path", [])) + ["promotion_lane", "canon_node"],
                    "derivation_receipt_refs": [packet_id, readiness_summary_id, replay_manifest_id, receipt_id],
                },
                "evidence": {
                    "evidence_class": claim["attributes"]["evidence"].get("evidence_class", "direct_quote"),
                    "evidence_ref_count": int(claim["attributes"]["evidence"].get("evidence_ref_count", 1)),
                    "burden_level": claim["attributes"]["evidence"].get("burden_level", "medium"),
                    "sufficiency_status": "sufficient",
                    "replayability_class": claim["attributes"]["evidence"].get("replayability_class", "high"),
                },
                "governance": {
                    "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                    "approval_level": "peer",
                    "actor_class": "compiler",
                    "risk_tier": claim["attributes"]["governance"].get("risk_tier", "medium"),
                    "promotion_tier": "promoted",
                    "freeze_class": "reviewed",
                },
                "semantic": {
                    "domain": claim["attributes"]["semantic"].get("domain", "prime-canon"),
                    "scope": "promoted-canon",
                    "claim_type": claim["spec"].get("claim_type", "assertion"),
                    "dependency_footprint": [],
                    "semantic_density": float(claim["attributes"]["semantic"].get("semantic_density", 0.80)),
                    "novelty_state": claim["attributes"]["semantic"].get("novelty_state", "unknown"),
                },
                "relational": {
                    "contradiction_refs": [],
                    "supersedes": [],
                    "superseded_by": [],
                    "depends_on": [claim_id, link_id],
                    "section_refs": [],
                    "cluster_refs": [],
                },
                "operational": {
                    "lane_ref": "promotion-lane",
                    "repo_home": node_rel_path,
                    "active_state": "active",
                    "mirror_permissions": "local_only",
                    "maintenance_burden": claim["attributes"]["operational"].get("maintenance_burden", "low"),
                    "route_destination": "current-state-view",
                },
                "temporal": {
                    "observed_at": claim["attributes"]["temporal"].get("observed_at"),
                    "reduced_at": now,
                    "status_since": now,
                    "replay_stability": claim["attributes"]["temporal"].get("replay_stability", "stable"),
                    "drift_sensitivity": claim["attributes"]["temporal"].get("drift_sensitivity", "low"),
                    "maturity": "working",
                },
            },
            "spec": {
                "canon_node_id": node_id,
                "originating_claim_ref": claim_id,
                "canonical_body": canonical_body,
                "state": state,
                "section_memberships": [],
                "active_projection_flags": ["machine_readable"],
                "confidence": confidence,
                "promotion_receipt_ref": receipt_id,
            },
        }

        ensure_required_fields(repo, NODE_KIND, node["spec"])
        validate_instance(repo, node)

        write_new(repo, repo / receipt_rel_path, receipt)
        write_new(repo, repo / node_rel_path, node)

        node_ids.append(node_id)
        node_receipt_ids.append(receipt_id)

    view_id = f"pc.current_state_view.{subject_slug}.v1"
    view_rel_path = f"views/current/{subject_slug}.yaml"
    view_hash = sha256_text("|".join(node_ids + node_receipt_ids + [packet_id, readiness_summary_id, replay_manifest_id, corpus_id]))

    current_view = {
        "kind": VIEW_KIND,
        "version": "v1",
        "metadata": {
            "object_id": view_id,
            "display_name": f"{subject_slug} current state view",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:promotion-lane-builder@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "current-state-view", "promoted"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": view_rel_path,
            },
            "lineage": {
                "source_refs": sorted(set(all_source_refs)),
                "source_unit_refs": sorted(set(all_source_unit_refs)),
                "reduction_path": ["promotion_lane", "current_state_view"],
                "derivation_receipt_refs": node_receipt_ids + [packet_id, readiness_summary_id, replay_manifest_id],
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
                "promotion_tier": "promoted",
                "freeze_class": "reviewed",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "current-state-view",
            },
            "relational": {
                "depends_on": node_ids + node_receipt_ids + [packet_id, readiness_summary_id, replay_manifest_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "promotion-lane",
                "repo_home": view_rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "render-projection",
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
            "view_id": view_id,
            "scope_ref": corpus_id,
            "active_node_refs": node_ids,
            "active_edge_refs": [],
            "active_contradiction_refs": [],
            "unresolved_blocker_refs": [],
            "view_hash": view_hash,
            "derivation_receipt_refs": node_receipt_ids + [packet_id, readiness_summary_id, replay_manifest_id],
            "rendered_projection_refs": [],
            "generated_at": now,
        },
    }

    ensure_required_fields(repo, VIEW_KIND, current_view["spec"])
    validate_instance(repo, current_view)

    lane_summary_id = f"pc.reduction_receipt.{subject_slug}.promotion-lane"
    lane_summary_rel_path = f"receipts/immutable/{subject_slug}/promotion-lane-summary.yaml"

    lane_summary = {
        "kind": RECEIPT_KIND,
        "version": "v1",
        "metadata": {
            "object_id": lane_summary_id,
            "display_name": f"{subject_slug} promotion lane summary",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:promotion-lane-builder@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "promotion", "summary"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": lane_summary_rel_path,
            },
            "lineage": {
                "source_refs": sorted(set(all_source_refs)),
                "source_unit_refs": sorted(set(all_source_unit_refs)),
                "reduction_path": ["promotion_lane", "summary_receipt"],
                "derivation_receipt_refs": node_receipt_ids + [packet_id, readiness_summary_id, replay_manifest_id],
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
                "promotion_tier": "promoted",
                "freeze_class": "reviewed",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "promotion-lane",
            },
            "relational": {
                "depends_on": target_claim_ids + node_ids + [view_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "promotion-lane",
                "repo_home": lane_summary_rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "render-projection",
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
            "decision_receipt_id": lane_summary_id,
            "target_ref": view_id,
            "decision_type": choose_enum(repo, RECEIPT_KIND, "decision_type", "promote", "include"),
            "deciding_surface": choose_enum(repo, RECEIPT_KIND, "deciding_surface", "compiler", "ci"),
            "rationale": f"promoted {len(node_ids)} ready candidate claims into canon nodes and generated current state view {view_id}; signed human approval sha256:{approval_hash}",
            "cited_receipt_refs": node_receipt_ids + [packet_id, readiness_summary_id],
            "cited_object_refs": target_claim_ids + node_ids + [view_id, replay_manifest_id],
            "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
            "reviewer_refs": [reviewer],
            "blocker_state": choose_enum(repo, RECEIPT_KIND, "blocker_state", "none", "present_resolved"),
            "route_outcome": choose_enum(repo, RECEIPT_KIND, "route_outcome", "promotion_lane", "deferred"),
        },
    }

    ensure_required_fields(repo, RECEIPT_KIND, lane_summary["spec"])
    validate_instance(repo, lane_summary)

    write_new(repo, repo / view_rel_path, current_view)
    write_new(repo, repo / lane_summary_rel_path, lane_summary)

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = "render-projection"
    corpus_stream.seek(0)
    corpus_stream.truncate()
    corpus_stream.write(yaml.safe_dump(corpus, sort_keys=False).encode("utf-8"))
    corpus_stream.flush()
    os.fsync(corpus_stream.fileno())
    corpus_stream.close()

    print(view_id)
    print(f"promoted_nodes={len(node_ids)}")
    print(f"node_receipts={len(node_receipt_ids)}")
    print(lane_summary_id)

if __name__ == "__main__":
    main()
