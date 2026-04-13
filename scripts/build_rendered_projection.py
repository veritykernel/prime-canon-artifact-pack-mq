#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_contract import choose_enum, ensure_required_fields, validate_instance

PROFILE_KIND = "PRIME_CANON_RENDER_PROFILE_V1"
PLAN_KIND = "PRIME_CANON_RENDER_PLAN_V1"
EXEC_KIND = "PRIME_CANON_RENDER_EXECUTION_RECEIPT_V1"
DRIFT_KIND = "PRIME_CANON_RENDER_DRIFT_RECEIPT_V1"
VIEW_KIND = "PRIME_CANON_CURRENT_STATE_VIEW_V1"
NODE_KIND = "PRIME_CANON_NODE_V1"

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

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
    node_dir = repo / "canon" / "nodes" / subject_slug
    receipt_dir = repo / "receipts" / "immutable" / subject_slug
    rendered_path = repo / "views" / "rendered" / f"{subject_slug}.md"

    profile_cfg_path = repo / "control" / "render" / "render-profile.default.yaml"
    order_cfg_path = repo / "control" / "render" / "render-order.default.yaml"
    targets_cfg_path = repo / "control" / "render" / "render-targets.default.yaml"
    redaction_cfg_path = repo / "control" / "render" / "render-redaction.default.yaml"

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
    profile_cfg = load_yaml(profile_cfg_path)
    order_cfg = load_yaml(order_cfg_path)
    targets_cfg = load_yaml(targets_cfg_path)
    redaction_cfg = load_yaml(redaction_cfg_path)

    corpus_id = corpus["spec"]["corpus_id"]
    view_id = view["spec"]["view_id"]
    now = utc_now()
    rendered_rel_path = f"views/rendered/{subject_slug}.md"
    execution_receipt_id = f"pc.render_execution_receipt.{subject_slug}.default"
    drift_receipt_id = f"pc.render_drift_receipt.{subject_slug}.default"
    plan_id = f"pc.render_plan.{subject_slug}.default"

    default_output_format = str(profile_cfg["default_output_format"])
    target_projection_flag = str(profile_cfg["target_projection_flag"])
    section_strategy = str(profile_cfg["section_strategy"])
    ordering_strategy = str(profile_cfg["ordering_strategy"])
    heading_style = str(profile_cfg["heading_style"])
    include_metadata_fields = list(profile_cfg.get("include_metadata_fields", []))
    include_receipt_footer = bool(profile_cfg.get("include_receipt_footer", False))
    redaction_policy_ref = str(profile_cfg["redaction_policy_ref"])
    render_order_ref = str(profile_cfg["render_order_ref"])
    render_targets_ref = str(profile_cfg["render_targets_ref"])

    allowed_projection_flags = list(targets_cfg["allowed_projection_flags"])
    default_projection_flags = list(targets_cfg["default_projection_flags"])
    allowed_output_formats = list(targets_cfg["allowed_output_formats"])

    if target_projection_flag not in allowed_projection_flags:
        raise SystemExit(f"target_projection_flag {target_projection_flag} not allowed by render-targets")
    if default_output_format not in allowed_output_formats:
        raise SystemExit(f"default_output_format {default_output_format} not allowed by render-targets")
    if str(order_cfg["ordering_mode"]) != "active_node_refs":
        raise SystemExit("only ordering_mode=active_node_refs is supported in this first cycle-2 render refactor")
    if str(redaction_cfg["policy_mode"]) != "none":
        raise SystemExit("only redaction policy_mode=none is supported in this first cycle-2 render refactor")
    if default_output_format != "markdown":
        raise SystemExit("only markdown output is supported in this first cycle-2 render refactor")
    if target_projection_flag != "rendered_text":
        raise SystemExit("this first cycle-2 render refactor expects target_projection_flag=rendered_text")

    render_profile = {
        "kind": PROFILE_KIND,
        "version": "v1",
        "metadata": {
            "object_id": str(profile_cfg["profile_id"]),
            "display_name": f"{subject_slug} render profile default",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:rendered-projection-builder@2.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "render-profile", "cycle-2"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": str(profile_cfg_path.relative_to(repo)),
            },
            "lineage": {
                "source_refs": [],
                "source_unit_refs": [],
                "reduction_path": ["render_profile_validate"],
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
                "risk_tier": "low",
                "promotion_tier": "promoted",
                "freeze_class": "reviewed",
            },
            "semantic": {
                "domain": "prime-canon",
                "scope": "render-profile",
            },
            "relational": {
                "depends_on": [render_order_ref, render_targets_ref, redaction_policy_ref],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "rendered-projection",
                "repo_home": str(profile_cfg_path.relative_to(repo)),
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
            "profile_id": str(profile_cfg["profile_id"]),
            "default_output_format": default_output_format,
            "target_projection_flag": target_projection_flag,
            "section_strategy": section_strategy,
            "ordering_strategy": ordering_strategy,
            "heading_style": heading_style,
            "include_metadata_fields": include_metadata_fields,
            "include_receipt_footer": include_receipt_footer,
            "redaction_policy_ref": redaction_policy_ref,
            "render_order_ref": render_order_ref,
            "render_targets_ref": render_targets_ref,
        },
    }

    ensure_required_fields(repo, PROFILE_KIND, render_profile["spec"])
    validate_instance(repo, render_profile)

    node_ids = list(view["spec"].get("active_node_refs", []))
    if not node_ids:
        raise SystemExit(f"current state view has no active_node_refs: {view_path}")

    render_plan = {
        "kind": PLAN_KIND,
        "version": "v1",
        "metadata": {
            "object_id": plan_id,
            "display_name": f"{subject_slug} render plan default",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:rendered-projection-builder@2.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "render-plan", "cycle-2"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": rendered_rel_path,
            },
            "lineage": {
                "source_refs": [],
                "source_unit_refs": [],
                "reduction_path": ["render_plan_validate"],
                "derivation_receipt_refs": list(view["spec"].get("derivation_receipt_refs", [])),
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
                "scope": "render-plan",
            },
            "relational": {
                "depends_on": node_ids + [view_id, str(profile_cfg["profile_id"])],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "rendered-projection",
                "repo_home": rendered_rel_path,
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
            "plan_id": plan_id,
            "scope_ref": corpus_id,
            "profile_ref": str(profile_cfg["profile_id"]),
            "current_state_view_ref": view_id,
            "target_node_refs": node_ids,
            "output_path": rendered_rel_path,
            "output_format": default_output_format,
            "target_projection_flag": target_projection_flag,
            "ordering_strategy": ordering_strategy,
            "section_strategy": section_strategy,
            "render_order_ref": render_order_ref,
            "redaction_policy_ref": redaction_policy_ref,
            "generated_from_ref": view_id,
        },
    }

    ensure_required_fields(repo, PLAN_KIND, render_plan["spec"])
    validate_instance(repo, render_plan)

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
        for item in default_projection_flags:
            if item == target_projection_flag and item not in flags:
                flags.append(item)
        if "machine_readable" not in flags:
            flags.insert(0, "machine_readable")

        ordered = []
        for item in ["machine_readable", "rendered_text", "exportable"]:
            if item in flags and item not in ordered:
                ordered.append(item)

        node["spec"]["active_projection_flags"] = ordered
        node["metadata"]["updated_at"] = now
        node["attributes"]["temporal"]["reduced_at"] = now
        node["attributes"]["temporal"]["status_since"] = now

        ensure_required_fields(repo, NODE_KIND, node["spec"])
        validate_instance(repo, node)
        node_path.write_text(yaml.safe_dump(node, sort_keys=False), encoding="utf-8")

        node_objects.append(node)
        all_source_refs.extend(node["attributes"]["lineage"].get("source_refs", []))
        all_source_unit_refs.extend(node["attributes"]["lineage"].get("source_unit_refs", []))

    lines = []
    title = f"{subject_slug} rendered canon"
    if heading_style == "title_only":
        lines.append(f"# {title}")
    else:
        lines.append(f"# {title}")
    lines.append("")

    metadata_map = {
        "corpus_id": corpus_id,
        "current_state_view": view_id,
        "generated_at": now,
    }

    for field in include_metadata_fields:
        if field in metadata_map:
            lines.append(f"- {field}: `{metadata_map[field]}`")
    lines.append(f"- active_node_count: `{len(node_objects)}`")
    lines.append("")

    lines.append("## Promoted canon nodes")
    lines.append("")

    if section_strategy != "linear_nodes":
        raise SystemExit(f"unsupported section_strategy in first cycle-2 render refactor: {section_strategy}")
    if ordering_strategy != "active_node_order":
        raise SystemExit(f"unsupported ordering_strategy in first cycle-2 render refactor: {ordering_strategy}")

    for idx, node in enumerate(node_objects, start=1):
        if heading_style == "numbered":
            lines.append(f"{idx}. {node['spec']['canonical_body']}")
        else:
            lines.append(f"- {node['spec']['canonical_body']}")

    if include_receipt_footer:
        lines.append("")
        lines.append("## Projection receipts")
        lines.append("")
        lines.append(f"- render_profile_ref: `{render_profile['spec']['profile_id']}`")
        lines.append(f"- render_plan_ref: `{plan_id}`")

    rendered_text = "\n".join(lines) + "\n"
    rendered_path.write_text(rendered_text, encoding="utf-8")
    output_sha256 = sha256_file(rendered_path)

    prior_receipts = [
        ref for ref in view["spec"].get("derivation_receipt_refs", [])
        if not ref.endswith(".rendered-projection")
        and not ref.endswith(".default")
    ]

    execution_receipt = {
        "kind": EXEC_KIND,
        "version": "v1",
        "metadata": {
            "object_id": execution_receipt_id,
            "display_name": f"{subject_slug} render execution receipt",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:rendered-projection-builder@2.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "render-execution", "cycle-2"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": f"receipts/immutable/{subject_slug}/render-execution.yaml",
            },
            "lineage": {
                "source_refs": sorted(set(all_source_refs)),
                "source_unit_refs": sorted(set(all_source_unit_refs)),
                "reduction_path": ["rendered_projection", "render_execution"],
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
                "scope": "render-execution",
            },
            "relational": {
                "depends_on": node_ids + [view_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "rendered-projection",
                "repo_home": f"receipts/immutable/{subject_slug}/render-execution.yaml",
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "export-prep",
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
            "execution_receipt_id": execution_receipt_id,
            "plan_ref": plan_id,
            "profile_ref": str(profile_cfg["profile_id"]),
            "target_view_ref": view_id,
            "output_ref": rendered_rel_path,
            "output_sha256": output_sha256,
            "rendered_node_count": len(node_objects),
            "rendered_projection_flag": target_projection_flag,
            "execution_status": choose_enum(repo, EXEC_KIND, "execution_status", "success", "partial"),
            "generated_at": now,
            "cited_object_refs": node_ids + [view_id],
            "drift_check_required": True,
        },
    }

    ensure_required_fields(repo, EXEC_KIND, execution_receipt["spec"])
    validate_instance(repo, execution_receipt)

    view["metadata"]["updated_at"] = now
    view["attributes"]["temporal"]["reduced_at"] = now
    view["attributes"]["temporal"]["status_since"] = now
    view["attributes"]["operational"]["route_destination"] = "export-prep"
    view["spec"]["rendered_projection_refs"] = [rendered_rel_path]
    view["spec"]["derivation_receipt_refs"] = prior_receipts + [execution_receipt_id, drift_receipt_id]
    view["spec"]["generated_at"] = now
    view["spec"]["view_hash"] = sha256_text(
        "|".join(
            node_ids
            + list(view["spec"].get("active_edge_refs", []))
            + list(view["spec"].get("active_contradiction_refs", []))
            + list(view["spec"].get("unresolved_blocker_refs", []))
            + [rendered_rel_path, execution_receipt_id, drift_receipt_id, corpus_id, now]
        )
    )

    ensure_required_fields(repo, VIEW_KIND, view["spec"])
    validate_instance(repo, view)
    view_path.write_text(yaml.safe_dump(view, sort_keys=False), encoding="utf-8")

    current_view_hash = view["spec"]["view_hash"]

    drift_receipt = {
        "kind": DRIFT_KIND,
        "version": "v1",
        "metadata": {
            "object_id": drift_receipt_id,
            "display_name": f"{subject_slug} render drift receipt",
            "created_at": now,
            "updated_at": now,
            "created_by": "compiler:rendered-projection-builder@2.0.0",
            "owners": ["team:prime-canon"],
            "tags": ["prime-canon", subject_slug, "render-drift", "cycle-2"],
        },
        "attributes": {
            "identity": {
                "corpus_id": corpus_id,
                "subject_slug": subject_slug,
                "canonical_home": f"receipts/immutable/{subject_slug}/render-drift.yaml",
            },
            "lineage": {
                "source_refs": sorted(set(all_source_refs)),
                "source_unit_refs": sorted(set(all_source_unit_refs)),
                "reduction_path": ["rendered_projection", "render_drift_check"],
                "derivation_receipt_refs": prior_receipts + [execution_receipt_id],
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
                "scope": "render-drift",
            },
            "relational": {
                "depends_on": node_ids + [view_id, execution_receipt_id],
                "cluster_refs": [],
                "section_refs": [],
            },
            "operational": {
                "lane_ref": "rendered-projection",
                "repo_home": f"receipts/immutable/{subject_slug}/render-drift.yaml",
                "active_state": "active",
                "mirror_permissions": "local_only",
                "route_destination": "export-prep",
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
            "plan_ref": plan_id,
            "target_view_ref": view_id,
            "output_ref": rendered_rel_path,
            "current_view_hash": current_view_hash,
            "output_sha256": output_sha256,
            "drift_status": choose_enum(repo, DRIFT_KIND, "drift_status", "in_sync", "stale_view"),
            "compared_at": now,
            "blocker": False,
            "recommended_route": choose_enum(repo, DRIFT_KIND, "recommended_route", "export_prep", "deferred"),
        },
    }

    ensure_required_fields(repo, DRIFT_KIND, drift_receipt["spec"])
    validate_instance(repo, drift_receipt)

    (repo / execution_receipt["attributes"]["identity"]["canonical_home"]).write_text(yaml.safe_dump(execution_receipt, sort_keys=False), encoding="utf-8")
    (repo / drift_receipt["attributes"]["identity"]["canonical_home"]).write_text(yaml.safe_dump(drift_receipt, sort_keys=False), encoding="utf-8")

    corpus["metadata"]["updated_at"] = now
    corpus["attributes"]["temporal"]["reduced_at"] = now
    corpus["attributes"]["temporal"]["status_since"] = now
    corpus["attributes"]["operational"]["route_destination"] = "export-prep"
    corpus_index_path.write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")

    print(render_profile["spec"]["profile_id"])
    print(plan_id)
    print(execution_receipt_id)
    print(drift_receipt_id)
    print(rendered_rel_path)
    print(f"rendered_nodes={len(node_ids)}")

if __name__ == "__main__":
    main()
