#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_contract import choose_enum, ensure_required_fields, validate_instance

VIEW_KIND = "PRIME_CANON_CURRENT_STATE_VIEW_V1"
NODE_KIND = "PRIME_CANON_NODE_V1"
RECEIPT_KIND = "PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"
    view_path = repo / "views" / "current" / f"{subject_slug}.yaml"
    node_dir = repo / "canon" / "nodes" / subject_slug
    receipt_dir = repo / "receipts" / "immutable" / subject_slug
    rendered_path = repo / "views" / "rendered" / f"{subject_slug}.md"

    if not corpus_index_path.exists():
        raise SystemExit(f"missing corpus index: {corpus_index_path}")
    if not view_path.exists():
        raise SystemExit(f"missing current state view: {view_path}")
    if not node_dir.exists():
        raise SystemExit(f"missing node dir: {node_dir}")
    if not receipt_dir.exists():
        raise SystemExit(f"missing receipt dir: {receipt_dir}")

    rendered_path.parent.mkdir(parents=True, exist_ok=True)

    corpus = yaml.safe_load(corpus_index_path.read_text(encoding="utf-8"))
    view = yaml.safe_load(view_path.read_text(encoding="utf-8"))

    corpus_id = corpus["spec"]["corpus_id"]
    view_id = view["spec"]["view_id"]
    now = utc_now()
    rendered_rel_path = f"views/rendered/{subject_slug}.md"

    node_ids = list(view["spec"].get("active_node_refs", []))
    if not node_ids:
        raise SystemExit(f"current state view has no active_node_refs: {view_path}")

    node_objects = []
    all_source_refs = []
    all_source_unit_refs = []

    for node_id in node_ids:
        seq = node_id.rsplit(".", 1)[-1]
        node_path = node_dir / f"node-{seq}.yaml"
        if not node_path.exists():
            raise SystemExit(f"missing node file for {node_id}: {node_path}")
        node = yaml.safe_load(node_path.read_text(encoding="utf-8"))

        flags = list(node["spec"].get("active_projection_flags", []))
        ordered = []
        for item in ["machine_readable", "rendered_text"]:
            if item not in flags:
                flags.append(item)
        for item in ["machine_readable", "rendered_text", "exportable"]:
            if item in flags:
                ordered.append(item)
        node["spec"]["active_projection_flags"] = ordered

        node["metadata"]["updated_at"] = now
        node["attributes"]["temporal"]["reduced_at"] = now
        node["attributes"]["temporal"]["status_since"] = now
        validate_instance(repo, node)
        node_path.write_text(yaml.safe_dump(node, sort_keys=False), encoding="utf-8")

        node_objects.append(node)
        all_source_refs.extend(node["attributes"]["lineage"].get("source_refs", []))
        all_source_unit_refs.extend(node["attributes"]["lineage"].get("source_unit_refs", []))

    lines = []
    lines.append(f"# {subject_slug} rendered canon")
    lines.append("")
    lines.append(f"- corpus_id: `{corpus_id}`")
    lines.append(f"- current_state_view: `{view_id}`")
    lines.append(f"- generated_at: `{now}`")
    lines.append(f"- active_node_count: `{len(node_objects)}`")
    lines.append("")
    lines.append("## Promoted canon nodes")
    lines.append("")

    for idx, node in enumerate(node_objects, start=1):
        lines.append(f"{idx}. {node['spec']['canonical_body']}")

    rendered_text = "\n".join(lines) + "\n"
    rendered_path.write_text(rendered_text, encoding="utf-8")

    summary_receipt_id = f"pc.reduction_receipt.{subject_slug}.rendered-projection"
    summary_rel_path = f"receipts/immutable/{subject_slug}/rendered-projection-summary.yaml"

    prior_receipts = list(view["spec"].get("derivation_receipt_refs", []))
    view["metadata"]["updated_at"] = now
    view["attributes"]["temporal"]["reduced_at"] = now
    view["attributes"]["temporal"]["status_since"] = now
    view["attributes"]["operational"]["route_destination"] = "export-prep"
    view["spec"]["rendered_projection_refs"] = [rendered_rel_path]
    view["spec"]["derivation_receipt_refs"] = prior_receipts + [summary_receipt_id]
    view["spec"]["generated_at"] = now
    view["spec"]["view_hash"] = sha256_text(
        "|".join(
            node_ids
            + list(view["spec"].get("active_edge_refs", []))
            + list(view["spec"].get("active_contradiction_refs", []))
            + list(view["spec"].get("unresolved_blocker_refs", []))
            + [rendered_rel_path]
            + prior_receipts
            + [summary_receipt_id, corpus_id, now]
        )
    )

    ensure_required_fields(repo, VIEW_KIND, view["spec"])
    validate_instance(repo, view)
    view_path.write_text(yaml.safe_dump(view, sort_keys=False), encoding="utf-8")

    receipt = {
        "kind": RECEIPT_KIND,
        "version": "v1",
        "metadata": {
            "object_id": summary_receipt_id,
            "display_name": f"{subject_slug} rendered projection summary",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:rendered-projection-builder@1.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "rendered-projection", "summary"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": summary_rel_path,
            },
            "lineage": {
                "source_refs": sorted(set(all_source_refs)),
                "source_unit_refs": sorted(set(all_source_unit_refs)),
                "reduction_path": ["rendered_projection_lane"],
                "derivation_receipt_refs": prior_receipts,
            },
            "evidence": {
                "burden_level": "medium",
                "sufficiency_status": "sufficient",
            },
            "governance": {
                "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                "approval_level": "peer",
                "actor_class": "compiler",
                "risk_tier": "low",
                "promotion_tier": "promoted",
                "freeze_class": "reviewed",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "rendered-projection",
            },
            "relational": {
                "depends_on": node_ids + [view_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "rendered-projection",
                "repo_home": summary_rel_path,
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "deferred",
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
            "target_ref": view_id,
            "decision_type": choose_enum(repo, RECEIPT_KIND, "decision_type", "include", "defer"),
            "deciding_surface": choose_enum(repo, RECEIPT_KIND, "deciding_surface", "compiler", "ci"),
            "rationale": f"rendered markdown projection {rendered_rel_path} emitted from current state view {view_id} for {len(node_ids)} promoted nodes",
            "cited_receipt_refs": prior_receipts,
            "cited_object_refs": node_ids + [view_id, rendered_rel_path],
            "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
            "reviewer_refs": [],
            "blocker_state": choose_enum(repo, RECEIPT_KIND, "blocker_state", "none", "present_resolved"),
            "route_outcome": choose_enum(repo, RECEIPT_KIND, "route_outcome", "deferred", "promotion_lane"),
        },
    }

    ensure_required_fields(repo, RECEIPT_KIND, receipt["spec"])
    validate_instance(repo, receipt)
    (repo / summary_rel_path).write_text(yaml.safe_dump(receipt, sort_keys=False), encoding="utf-8")

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = "export-prep"
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

    print(view_id)
    print(rendered_rel_path)
    print(summary_receipt_id)
    print(f"rendered_nodes={len(node_ids)}")

if __name__ == "__main__":
    main()
