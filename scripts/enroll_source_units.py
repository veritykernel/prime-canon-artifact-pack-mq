#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REQUIRED_COLUMNS = [
    "seq",
    "source_ref",
    "locator",
    "start",
    "end",
    "observed_at",
    "scope",
    "normalized_text",
]

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_tsv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        if reader.fieldnames is None:
            raise SystemExit(f"TSV has no header: {path}")
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise SystemExit(f"TSV missing required columns {missing}: {path}")
        rows = []
        for idx, row in enumerate(reader, start=2):
            if not any((row.get(k) or "").strip() for k in row.keys()):
                continue
            clean = {k: (v.strip() if isinstance(v, str) else "") for k, v in row.items()}
            for col in REQUIRED_COLUMNS:
                if not clean.get(col):
                    raise SystemExit(f"{path}:{idx}: missing required value for {col}")
            rows.append(clean)
        if not rows:
            raise SystemExit(f"No source rows found in {path}")
        return rows

def sha256_text(parts):
    payload = "|".join(parts).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()

def main():
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("SUBJECT_SLUG", "subject-0001")
    tsv_path = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else repo / "work_orders" / subject_slug / "source-units.tsv"

    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"
    if not corpus_index_path.exists():
        raise SystemExit(f"Missing corpus index: {corpus_index_path}")
    rows = load_tsv(tsv_path)

    with corpus_index_path.open("r", encoding="utf-8") as fh:
        corpus = yaml.safe_load(fh)

    corpus_id = corpus["spec"]["corpus_id"]
    now = utc_now()
    created_by = os.environ.get("SOURCE_UNIT_CREATED_BY", "human:operator")
    owners = [x for x in os.environ.get("SOURCE_UNIT_OWNERS", "team:prime-canon").split(",") if x]
    tags = [x for x in os.environ.get("SOURCE_UNIT_TAGS", f"prime-canon,{subject_slug},source-unit").split(",") if x]

    source_unit_ids = []
    source_refs = []

    target_dir = repo / "canon" / "source_units" / subject_slug
    target_dir.mkdir(parents=True, exist_ok=True)

    for row in rows:
        seq_num = int(row["seq"])
        seq = f"{seq_num:04d}"
        object_id = f"pc.source_unit.{subject_slug}.{seq}"
        rel_path = f"canon/source_units/{subject_slug}/unit-{seq}.yaml"
        source_unit_ids.append(object_id)
        if row["source_ref"] not in source_refs:
            source_refs.append(row["source_ref"])

        source_kind = row.get("source_kind", "") or "chat_message"
        burden_level = row.get("burden_level", "") or "medium"
        sufficiency_status = row.get("sufficiency_status", "") or "sufficient"
        evidence_class = row.get("evidence_class", "") or "direct_quote"
        risk_tier = row.get("risk_tier", "") or "medium"
        semantic_density = float(row.get("semantic_density", "") or "0.80")
        novelty_state = row.get("novelty_state", "") or "unknown"
        drift_sensitivity = row.get("drift_sensitivity", "") or "medium"
        maintenance_burden = row.get("maintenance_burden", "") or "low"
        replay_stability = row.get("replay_stability", "") or "stable"
        maturity = row.get("maturity", "") or "working"

        normalized_text = row["normalized_text"]
        checksum = sha256_text([
            row["source_ref"],
            row["locator"],
            row["start"],
            row["end"],
            normalized_text,
        ])

        data = {
            "kind": "PRIME_CANON_SOURCE_UNIT_V1",
            "version": "v1",
            "metadata": {
                "object_id": object_id,
                "display_name": row.get("display_name", "") or f"{subject_slug} source unit {seq}",
                "created_at": now,
                "updated_at": now,
                "created_by": created_by,
                "owners": owners,
                "tags": tags,
            },
            "attributes": {
                "identity": {
                    "corpus_id": corpus_id,
                    "subject_slug": subject_slug,
                    "canonical_home": rel_path,
                },
                "lineage": {
                    "source_refs": [row["source_ref"]],
                    "source_unit_refs": [],
                    "reduction_path": ["intake"],
                    "derivation_receipt_refs": [],
                },
                "evidence": {
                    "burden_level": burden_level,
                    "sufficiency_status": sufficiency_status,
                    "evidence_class": evidence_class,
                    "evidence_ref_count": 1,
                    "replayability_class": "high",
                },
                "governance": {
                    "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                    "approval_level": "peer",
                    "actor_class": "human",
                    "risk_tier": risk_tier,
                    "promotion_tier": "draft",
                    "freeze_class": "reviewed",
                },
                "semantic": {
                    "domain": "prime-canon",
                    "scope": row["scope"],
                    "dependency_footprint": [],
                    "semantic_density": semantic_density,
                    "novelty_state": novelty_state,
                },
                "relational": {
                    "contradiction_refs": [],
                    "supersedes": [],
                    "superseded_by": [],
                    "depends_on": [],
                    "section_refs": [],
                    "cluster_refs": [],
                },
                "operational": {
                    "lane_ref": "intake",
                    "repo_home": rel_path,
                    "active_state": "active",
                    "mirror_permissions": "local_only",
                    "maintenance_burden": maintenance_burden,
                    "route_destination": "reduction",
                },
                "temporal": {
                    "status_since": now,
                    "replay_stability": replay_stability,
                    "drift_sensitivity": drift_sensitivity,
                    "maturity": maturity,
                    "observed_at": row["observed_at"],
                    "reduced_at": now,
                },
            },
            "spec": {
                "source_unit_id": object_id,
                "corpus_id": corpus_id,
                "source_ref": row["source_ref"],
                "span_ref": {
                    "locator": row["locator"],
                    "start": int(row["start"]),
                    "end": int(row["end"]),
                },
                "normalized_text": normalized_text,
                "extraction_method": row.get("extraction_method", "") or "message-span-normalize@1.0.0",
                "source_kind": source_kind,
                "checksum": checksum,
            },
        }

        out_path = repo / rel_path
        out_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["lineage"]["source_refs"] = source_refs
    corpus["attributes"]["lineage"]["source_unit_refs"] = source_unit_ids
    corpus["attributes"]["evidence"]["evidence_ref_count"] = len(source_refs)
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["spec"]["source_refs"] = source_refs
    corpus["spec"]["source_count"] = len(source_refs)
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

if __name__ == "__main__":
    main()
