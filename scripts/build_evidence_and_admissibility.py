#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_contract import choose_enum, ensure_enum, ensure_required_fields, validate_instance

EVIDENCE_LINK_KIND = "PRIME_CANON_EVIDENCE_LINK_V1"
ADMISSIBILITY_KIND = "PRIME_CANON_ADMISSIBILITY_DECISION_V1"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def source_trust_class_for(repo: Path, evidence_class: str) -> str:
    # evidence_class is copied from a contributor-authored claim. It cannot
    # establish the provenance or quality of the underlying source.
    return choose_enum(repo, EVIDENCE_LINK_KIND, "source_trust_class", "unrated")

def admissibility_weight_for(evidence_class: str, sufficiency_status: str, source_refs: list[str], source_unit_refs: list[str]) -> float:
    # Presence and labels in the same author-controlled pack are not an
    # independent admissibility assessment.
    return 0.0

def support_type_for(repo: Path, evidence_class: str, sufficiency_status: str) -> str:
    return choose_enum(repo, EVIDENCE_LINK_KIND, "support_type", "contextualizes", "weak_support")

def support_strength_for(repo: Path, evidence_class: str, sufficiency_status: str) -> str:
    return choose_enum(repo, EVIDENCE_LINK_KIND, "support_strength", "low")

def pass_fail_for(repo: Path, unmet_burdens: list[str]) -> str:
    preferred = "fail" if unmet_burdens else "pass"
    return choose_enum(repo, ADMISSIBILITY_KIND, "pass_fail", preferred, "provisional")

def write_new(repo: Path, path: Path, obj: dict) -> None:
    if not path.parent.resolve().is_relative_to(repo):
        raise SystemExit(f"output path escapes repository: {path}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(yaml.safe_dump(obj, sort_keys=False))

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    claim_dir = repo / "canon" / "candidate_claims" / subject_slug
    evidence_dir = repo / "canon" / "evidence_links" / subject_slug
    receipt_dir = repo / "receipts" / "immutable" / subject_slug
    corpus_index_path = repo / "canon" / "corpora" / subject_slug / "index.yaml"

    if not claim_dir.exists():
        raise SystemExit(f"missing candidate claim dir: {claim_dir}")
    if not corpus_index_path.exists():
        raise SystemExit(f"missing corpus index: {corpus_index_path}")

    for directory in (evidence_dir, receipt_dir):
        if directory.is_symlink() or not directory.resolve().is_relative_to(repo):
            raise SystemExit(f"output directory is not a repository directory: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

    claim_files = sorted(
        p for p in claim_dir.glob("claim-*.yaml")
        if p.is_file()
    )
    if not claim_files:
        raise SystemExit(f"no candidate claim files found in {claim_dir}")

    # A regenerated compiler receipt must not replace an immutable decision.
    for claim_path in claim_files:
        seq = claim_path.stem.replace("claim-", "")
        if any(path.exists() or path.is_symlink() for path in
               (evidence_dir / f"link-{seq}.yaml", receipt_dir / f"admissibility-{seq}.yaml")):
            raise SystemExit(f"prior evidence or admissibility output exists for {seq}; reconcile before rebuilding")

    corpus = yaml.safe_load(corpus_index_path.read_text(encoding="utf-8"))
    corpus_id = corpus["spec"]["corpus_id"]
    now = utc_now()

    built_link_ids = []
    built_decision_ids = []

    for claim_path in claim_files:
        claim = yaml.safe_load(claim_path.read_text(encoding="utf-8"))
        seq = claim_path.stem.replace("claim-", "")
        claim_id = claim["spec"]["claim_id"]
        source_refs = list(claim["attributes"]["lineage"].get("source_refs", []))
        source_unit_refs = list(claim["attributes"]["lineage"].get("source_unit_refs", []))
        evidence_class = claim["attributes"]["evidence"].get("evidence_class", "direct_quote")
        sufficiency_status = claim["attributes"]["evidence"].get("sufficiency_status", "insufficient")
        burden_level = claim["attributes"]["evidence"].get("burden_level", "medium")
        replayability_class = claim["attributes"]["evidence"].get("replayability_class", "high")
        semantic_density = float(claim["attributes"]["semantic"].get("semantic_density", 0.80))
        novelty_state = claim["attributes"]["semantic"].get("novelty_state", "unknown")
        domain = claim["attributes"]["semantic"].get("domain", "prime-canon")
        scope = claim["attributes"]["semantic"].get("scope", "intake-first-pass")
        risk_tier = claim["attributes"]["governance"].get("risk_tier", "medium")
        maintenance_burden = claim["attributes"]["operational"].get("maintenance_burden", "low")
        observed_at = claim["attributes"]["temporal"].get("observed_at")
        replay_stability = claim["attributes"]["temporal"].get("replay_stability", "stable")
        drift_sensitivity = claim["attributes"]["temporal"].get("drift_sensitivity", "medium")

        link_id = f"pc.evidence_link.{subject_slug}.{seq}"
        link_rel_path = f"canon/evidence_links/{subject_slug}/link-{seq}.yaml"
        evidence_ref = source_unit_refs[0] if source_unit_refs else (source_refs[0] if source_refs else "")
        source_trust_class = source_trust_class_for(repo, evidence_class)
        admissibility_weight = admissibility_weight_for(evidence_class, sufficiency_status, source_refs, source_unit_refs)
        support_type = support_type_for(repo, evidence_class, sufficiency_status)
        support_strength = support_strength_for(repo, evidence_class, sufficiency_status)

        ensure_enum(repo, EVIDENCE_LINK_KIND, "evidence_class", evidence_class)
        ensure_enum(repo, EVIDENCE_LINK_KIND, "support_type", support_type)
        ensure_enum(repo, EVIDENCE_LINK_KIND, "support_strength", support_strength)
        ensure_enum(repo, EVIDENCE_LINK_KIND, "source_trust_class", source_trust_class)

        evidence_link = {
            "kind": EVIDENCE_LINK_KIND,
            "version": "v1",
            "metadata": {
                "object_id": link_id,
                "display_name": f"{subject_slug} evidence link {seq}",
                "created_at": now,
                "updated_at": now,
                "created_by": "compiler:evidence-link-builder@1.1.0",
                "owners": ["team:prime-canon"],
                "tags": ["prime-canon", subject_slug, "evidence-link", "schema-driven"],
            },
            "attributes": {
                "identity": {
                    "corpus_id": corpus_id,
                    "subject_slug": subject_slug,
                    "canonical_home": link_rel_path,
                },
                "lineage": {
                    "source_refs": source_refs,
                    "source_unit_refs": source_unit_refs,
                    "reduction_path": list(claim["attributes"]["lineage"].get("reduction_path", [])) + ["evidence_link_build"],
                    "derivation_receipt_refs": [],
                },
                "evidence": {
                    "evidence_class": evidence_class,
                    "evidence_ref_count": max(len(source_refs), 1),
                    "burden_level": burden_level,
                    "sufficiency_status": sufficiency_status,
                    "replayability_class": replayability_class,
                },
                "governance": {
                    "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                    "approval_level": "peer",
                    "actor_class": "compiler",
                    "risk_tier": risk_tier,
                    "promotion_tier": "candidate",
                    "freeze_class": "mutable",
                },
                "semantic": {
                    "domain": domain,
                    "scope": scope,
                    "dependency_footprint": [],
                    "semantic_density": semantic_density,
                    "novelty_state": novelty_state,
                },
                "relational": {
                    "contradiction_refs": [],
                    "supersedes": [],
                    "superseded_by": [],
                    "depends_on": [claim_id],
                    "section_refs": [],
                    "cluster_refs": [],
                },
                "operational": {
                    "lane_ref": "evidence-link-admissibility",
                    "repo_home": link_rel_path,
                    "mirror_permissions": "local_only",
                    "active_state": "active",
                    "maintenance_burden": maintenance_burden,
                    "route_destination": "admissibility",
                },
                "temporal": {
                    "observed_at": observed_at,
                    "reduced_at": now,
                    "status_since": now,
                    "replay_stability": replay_stability,
                    "drift_sensitivity": drift_sensitivity,
                    "maturity": "working",
                },
            },
            "spec": {
                "link_id": link_id,
                "claim_ref": claim_id,
                "evidence_ref": evidence_ref,
                "evidence_class": evidence_class,
                "support_type": support_type,
                "support_strength": support_strength,
                "source_trust_class": source_trust_class,
                "admissibility_weight": admissibility_weight,
                "replayable": True,
            },
        }

        ensure_required_fields(repo, EVIDENCE_LINK_KIND, evidence_link["spec"])
        validate_instance(repo, evidence_link)

        decision_id = f"pc.admissibility_decision.{subject_slug}.{seq}"
        decision_rel_path = f"receipts/immutable/{subject_slug}/admissibility-{seq}.yaml"

        met_burdens = []
        unmet_burdens = []
        reasons = []

        if source_refs:
            met_burdens.append("source_refs_present")
            reasons.append("claim carries source_refs lineage")
        else:
            unmet_burdens.append("source_refs_present")

        if source_unit_refs:
            met_burdens.append("source_unit_refs_present")
            reasons.append("claim carries source_unit_refs lineage")
        else:
            unmet_burdens.append("source_unit_refs_present")

        if sufficiency_status == "sufficient":
            met_burdens.append("evidence_status_sufficient")
            reasons.append("claim evidence sufficiency_status is sufficient")
        else:
            unmet_burdens.append("evidence_status_sufficient")

        if evidence_class == "direct_quote":
            reasons.append("claim labels its evidence as a direct quote; source not independently verified")
        else:
            unmet_burdens.append("direct_quote_support")

        unmet_burdens.append("independent_source_verification")
        reasons.append("compiler cannot attest source authenticity or evidence sufficiency from contributor-authored labels")

        reasons.append(f"linked_evidence_ref={link_id}")

        pass_fail = pass_fail_for(repo, unmet_burdens)
        deciding_surface = choose_enum(repo, ADMISSIBILITY_KIND, "deciding_surface", "compiler", "human")

        admissibility = {
            "kind": ADMISSIBILITY_KIND,
            "version": "v1",
            "metadata": {
                "object_id": decision_id,
                "display_name": f"{subject_slug} admissibility decision {seq}",
                "created_at": now,
                "updated_at": now,
                "created_by": "compiler:admissibility-builder@1.1.0",
                "owners": ["team:prime-canon"],
                "tags": ["prime-canon", subject_slug, "admissibility", "schema-driven"],
            },
            "attributes": {
                "identity": {
                    "corpus_id": corpus_id,
                    "subject_slug": subject_slug,
                    "canonical_home": decision_rel_path,
                },
                "lineage": {
                    "source_refs": source_refs,
                    "source_unit_refs": source_unit_refs,
                    "reduction_path": list(claim["attributes"]["lineage"].get("reduction_path", [])) + ["evidence_link_build", "admissibility_decision"],
                    "derivation_receipt_refs": [link_id],
                },
                "evidence": {
                    "evidence_class": evidence_class,
                    "evidence_ref_count": max(len(source_refs), 1),
                    "burden_level": burden_level,
                    "sufficiency_status": sufficiency_status,
                    "replayability_class": replayability_class,
                },
                "governance": {
                    "jurisdiction_ref": "pc.jurisdiction.human-reviewer",
                    "approval_level": "peer",
                    "actor_class": "compiler",
                    "risk_tier": risk_tier,
                    "promotion_tier": "candidate",
                    "freeze_class": "reviewed",
                },
                "semantic": {
                    "domain": domain,
                    "scope": scope,
                    "dependency_footprint": [],
                    "semantic_density": semantic_density,
                    "novelty_state": novelty_state,
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
                    "lane_ref": "evidence-link-admissibility",
                    "repo_home": decision_rel_path,
                    "mirror_permissions": "local_only",
                    "active_state": "active",
                    "maintenance_burden": maintenance_burden,
                    "route_destination": "contradiction",
                },
                "temporal": {
                    "observed_at": observed_at,
                    "reduced_at": now,
                    "status_since": now,
                    "replay_stability": replay_stability,
                    "drift_sensitivity": drift_sensitivity,
                    "maturity": "working",
                },
            },
            "spec": {
                "decision_id": decision_id,
                "target_claim_ref": claim_id,
                "profile_ref": "pc.admissibility.default.v1",
                "pass_fail": pass_fail,
                "met_burdens": met_burdens,
                "unmet_burdens": unmet_burdens,
                "reasons": reasons,
                "deciding_surface": deciding_surface,
                "override_used": False,
            },
        }

        ensure_required_fields(repo, ADMISSIBILITY_KIND, admissibility["spec"])
        validate_instance(repo, admissibility)

        write_new(repo, repo / link_rel_path, evidence_link)
        write_new(repo, repo / decision_rel_path, admissibility)

        built_link_ids.append(link_id)
        built_decision_ids.append(decision_id)

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = "contradiction"
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

    print(f"generated {len(built_link_ids)} evidence links for {subject_slug}")
    for ref in built_link_ids:
        print(ref)
    print(f"generated {len(built_decision_ids)} admissibility decisions for {subject_slug}")
    for ref in built_decision_ids:
        print(ref)

if __name__ == "__main__":
    main()
