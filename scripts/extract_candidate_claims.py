#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def slug_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "claim"

def phrase_from_text(text: str, max_len: int = 96) -> str:
    t = " ".join(text.strip().split())
    if len(t) <= max_len:
        return t
    cut = t[:max_len].rsplit(" ", 1)[0].strip()
    return (cut if cut else t[:max_len]).rstrip(" .,;:!?")

def merge_key_for(text: str) -> str:
    normalized = " ".join(text.strip().lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"mk.{slug_text(normalized[:48])}.{digest}"

def infer_claim_type(locator: str, text: str) -> str:
    loc = locator.lower()
    t = text.strip()
    if "question" in loc or t.endswith("?"):
        return "question"
    if "thesis" in loc:
        return "thesis"
    if t.lower().startswith("should "):
        return "question"
    return "assertion"

def extraction_confidence_for(unit: dict) -> float:
    density = float(unit["attributes"]["semantic"].get("semantic_density", 0.80))
    evidence_class = unit["attributes"]["evidence"].get("evidence_class", "direct_quote")
    sufficiency = unit["attributes"]["evidence"].get("sufficiency_status", "sufficient")
    score = 0.80
    if evidence_class == "direct_quote":
        score += 0.08
    if sufficiency == "sufficient":
        score += 0.04
    score += min(max(density - 0.80, 0.0), 0.15)
    return round(min(score, 0.98), 2)

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    source_dir = repo / "canon" / "source_units" / subject_slug
    claim_dir = repo / "canon" / "candidate_claims" / subject_slug
    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"

    if not source_dir.exists():
        raise SystemExit(f"missing source unit dir: {source_dir}")
    if not corpus_index_path.exists():
        raise SystemExit(f"missing corpus index: {corpus_index_path}")

    claim_dir.mkdir(parents=True, exist_ok=True)

    source_files = sorted(
        p for p in source_dir.glob("unit-*.yaml")
        if p.is_file()
    )
    if not source_files:
        raise SystemExit(f"no source unit files found in {source_dir}")

    corpus = yaml.safe_load(corpus_index_path.read_text(encoding="utf-8"))
    corpus_id = corpus["spec"]["corpus_id"]
    now = utc_now()

    generated_ids = []
    for src_path in source_files:
        unit = yaml.safe_load(src_path.read_text(encoding="utf-8"))
        unit_id = unit["spec"]["source_unit_id"]
        seq = src_path.stem.replace("unit-", "")
        normalized_text = unit["spec"]["normalized_text"].strip()
        locator = unit["spec"]["span_ref"]["locator"]

        claim_id = f"pc.candidate_claim.{subject_slug}.{seq}"
        rel_path = f"canon/candidate_claims/{subject_slug}/claim-{seq}.yaml"
        claim_type = infer_claim_type(locator, normalized_text)
        canonical_phrase = phrase_from_text(normalized_text)
        merge_key = merge_key_for(normalized_text)

        claim = {
            "kind": "PRIME_CANON_CANDIDATE_CLAIM_V1",
            "version": "v1",
            "metadata": {
                "object_id": claim_id,
                "display_name": f"{subject_slug} candidate claim {seq}",
                "created_at": now,
                "updated_at": now,
                "created_by": "compiler:candidate-claim-extractor@1.0.0",
                "owners": ["team:prime-canon"],
                "tags": ["prime-canon", subject_slug, "candidate-claim", "first-pass"],
            },
            "attributes": {
                "identity": {
                    "corpus_id": corpus_id,
                    "subject_slug": subject_slug,
                    "canonical_home": rel_path,
                },
                "lineage": {
                    "source_refs": list(unit["attributes"]["lineage"].get("source_refs", [])),
                    "source_unit_refs": [unit_id],
                    "reduction_path": list(unit["attributes"]["lineage"].get("reduction_path", [])) + ["candidate_claim_extraction"],
                    "derivation_receipt_refs": [],
                },
                "evidence": {
                    "evidence_class": unit["attributes"]["evidence"].get("evidence_class", "direct_quote"),
                    "evidence_ref_count": int(unit["attributes"]["evidence"].get("evidence_ref_count", 1)),
                    "burden_level": unit["attributes"]["evidence"].get("burden_level", "medium"),
                    "sufficiency_status": unit["attributes"]["evidence"].get("sufficiency_status", "sufficient"),
                    "replayability_class": unit["attributes"]["evidence"].get("replayability_class", "high"),
                },
                "governance": {
                    "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                    "approval_level": "peer",
                    "actor_class": "compiler",
                    "risk_tier": unit["attributes"]["governance"].get("risk_tier", "medium"),
                    "promotion_tier": "candidate",
                    "freeze_class": "mutable",
                },
                "semantic": {
                    "domain": unit["attributes"]["semantic"].get("domain", "prime-canon"),
                    "scope": unit["attributes"]["semantic"].get("scope", "intake-first-pass"),
                    "claim_type": claim_type,
                    "dependency_footprint": [],
                    "semantic_density": float(unit["attributes"]["semantic"].get("semantic_density", 0.80)),
                    "novelty_state": unit["attributes"]["semantic"].get("novelty_state", "unknown"),
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
                    "lane_ref": "candidate-claim-extraction",
                    "repo_home": rel_path,
                    "mirror_permissions": "local_only",
                    "active_state": "active",
                    "maintenance_burden": unit["attributes"]["operational"].get("maintenance_burden", "low"),
                    "route_destination": "admissibility",
                },
                "temporal": {
                    "observed_at": unit["attributes"]["temporal"].get("observed_at"),
                    "reduced_at": now,
                    "status_since": now,
                    "replay_stability": unit["attributes"]["temporal"].get("replay_stability", "stable"),
                    "drift_sensitivity": unit["attributes"]["temporal"].get("drift_sensitivity", "medium"),
                    "maturity": "working",
                },
            },
            "spec": {
                "claim_id": claim_id,
                "corpus_id": corpus_id,
                "canonical_phrase": canonical_phrase,
                "normalized_claim_body": normalized_text,
                "claim_type": claim_type,
                "source_unit_refs": [unit_id],
                "claim_scope": unit["attributes"]["semantic"].get("scope", "intake-first-pass"),
                "claim_domain": unit["attributes"]["semantic"].get("domain", "prime-canon"),
                "extraction_confidence": extraction_confidence_for(unit),
                "candidate_state": "candidate",
                "merge_key": merge_key,
            },
        }

        out_path = repo / rel_path
        out_path.write_text(yaml.safe_dump(claim, sort_keys=False), encoding="utf-8")
        generated_ids.append(claim_id)

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = "admissibility"
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

    print(f"generated {len(generated_ids)} candidate claims for {subject_slug}")
    for claim_id in generated_ids:
        print(claim_id)

if __name__ == "__main__":
    main()
