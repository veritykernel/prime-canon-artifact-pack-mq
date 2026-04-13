#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_contract import ensure_required_fields, validate_instance

DRIFT_KIND = "PRIME_CANON_RENDER_DRIFT_RECEIPT_V1"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_yaml(path: Path):
    if not path.exists():
        raise SystemExit(f"missing yaml: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"
    view_path = repo / "views" / "current" / f"{subject_slug}.yaml"
    execution_path = repo / "receipts" / "immutable" / subject_slug / "render-execution.yaml"
    drift_path = repo / "receipts" / "immutable" / subject_slug / "render-drift.yaml"

    corpus = load_yaml(corpus_index_path)
    view = load_yaml(view_path)
    execution = load_yaml(execution_path)
    prior_drift = load_yaml(drift_path) if drift_path.exists() else None

    corpus_id = corpus["spec"]["corpus_id"]
    view_id = execution["spec"]["target_view_ref"]
    plan_ref = execution["spec"]["plan_ref"]
    output_ref = execution["spec"]["output_ref"]
    output_path = repo / output_ref
    current_view_hash = view["spec"]["view_hash"]
    expected_output_sha = execution["spec"]["output_sha256"]
    baseline_view_hash = prior_drift["spec"]["current_view_hash"] if prior_drift else current_view_hash
    now = utc_now()

    created_at = prior_drift["metadata"]["created_at"] if prior_drift else now
    drift_receipt_id = execution["metadata"]["object_id"].replace("pc.render_execution_receipt", "pc.render_drift_receipt")

    if not output_path.exists():
        drift_status = "missing_output"
        blocker = True
        recommended_route = "render_refresh"
        current_output_sha = expected_output_sha
    else:
        current_output_sha = sha256_file(output_path)
        if current_output_sha != expected_output_sha:
            drift_status = "out_of_sync"
            blocker = True
            recommended_route = "render_refresh"
        elif current_view_hash != baseline_view_hash:
            drift_status = "stale_view"
            blocker = True
            recommended_route = "render_refresh"
        else:
            drift_status = "in_sync"
            blocker = False
            recommended_route = "export_prep"

    drift_receipt = {
        "kind": DRIFT_KIND,
        "version": "v1",
        "metadata": {
            "object_id": drift_receipt_id,
            "display_name": f"{subject_slug} render drift receipt",
            "created_at": created_at,
            "updated_at": now,
            "created_by": "compiler:render-drift-check@2.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "render-drift", "check"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": f"receipts/immutable/{subject_slug}/render-drift.yaml",
            },
            "lineage": {
                "source_refs": list(view["attributes"]["lineage"].get("source_refs", [])),
                "source_unit_refs": list(view["attributes"]["lineage"].get("source_unit_refs", [])),
                "reduction_path": ["render_drift_check"],
                "derivation_receipt_refs": [execution["metadata"]["object_id"]],
            },
            "evidence": {
                "burden_level": "medium",
                "sufficiency_status": "sufficient" if not blocker else "insufficient",
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
                "scope": "render-drift-check",
            },
            "relational": {
                "depends_on": list(view["spec"].get("active_node_refs", [])) + [view_id, execution["metadata"]["object_id"]],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "render-drift-check",
                "repo_home": f"receipts/immutable/{subject_slug}/render-drift.yaml",
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": recommended_route,
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
            "drift_receipt_id": drift_receipt_id,
            "plan_ref": plan_ref,
            "target_view_ref": view_id,
            "output_ref": output_ref,
            "current_view_hash": current_view_hash,
            "output_sha256": current_output_sha,
            "drift_status": drift_status,
            "compared_at": now,
            "blocker": blocker,
            "recommended_route": recommended_route,
        },
    }

    ensure_required_fields(repo, DRIFT_KIND, drift_receipt["spec"])
    validate_instance(repo, drift_receipt)
    drift_path.write_text(yaml.safe_dump(drift_receipt, sort_keys=False), encoding="utf-8")

    view["metadata"]["updated_at"] = now
    view["attributes"]["temporal"]["reduced_at"] = now
    view["attributes"]["temporal"]["status_since"] = now
    view["attributes"]["operational"]["route_destination"] = recommended_route
    view_path.write_text(yaml.safe_dump(view, sort_keys=False), encoding="utf-8")

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = recommended_route
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

    print(drift_receipt_id)
    print(f"drift_status={drift_status}")
    print(f"blocker={str(blocker).lower()}")
    print(f"recommended_route={recommended_route}")

if __name__ == "__main__":
    main()
