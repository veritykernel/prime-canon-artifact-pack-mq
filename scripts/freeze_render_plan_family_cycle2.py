#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

RENDER_PROFILE_KIND = "PRIME_CANON_RENDER_PROFILE_V1"
RENDER_PLAN_KIND = "PRIME_CANON_RENDER_PLAN_V1"
RENDER_EXECUTION_RECEIPT_KIND = "PRIME_CANON_RENDER_EXECUTION_RECEIPT_V1"
RENDER_DRIFT_RECEIPT_KIND = "PRIME_CANON_RENDER_DRIFT_RECEIPT_V1"

def id_string():
    return {"type": "string", "pattern": "^[A-Za-z0-9._:/-]+$"}

def nonempty_string():
    return {"type": "string", "minLength": 1}

def string_array(pattern: str | None = None, min_items: int | None = None):
    item = {"type": "string"}
    if pattern is not None:
        item["pattern"] = pattern
    out = {"type": "array", "items": item}
    if min_items is not None:
        out["minItems"] = min_items
    return out

def enum_string(values: list[str]):
    return {"type": "string", "enum": values}

def boolean():
    return {"type": "boolean"}

def integer_min(minimum: int):
    return {"type": "integer", "minimum": minimum}

def number_range(minimum: float, maximum: float):
    return {"type": "number", "minimum": minimum, "maximum": maximum}

def datetime_string():
    return {"type": "string", "format": "date-time"}

def sha256_hex():
    return {"type": "string", "pattern": "^[a-f0-9]{64}$"}

def clone_with_new_spec(defs: dict, base_kind: str, new_kind: str, description: str, spec_properties: dict, spec_required: list[str]) -> dict:
    schema = copy.deepcopy(defs[base_kind])
    schema["description"] = description
    schema["properties"]["kind"] = {"const": new_kind}
    schema["properties"]["spec"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": spec_properties,
        "required": spec_required,
    }
    return schema

def main() -> None:
    bundle_path = Path("schemas/prime-canon-bundle.schema.json")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    defs = bundle["$defs"]

    render_profile_spec = {
        "profile_id": id_string(),
        "default_output_format": enum_string(["markdown", "yaml", "json"]),
        "target_projection_flag": enum_string(["machine_readable", "rendered_text", "exportable"]),
        "section_strategy": enum_string(["linear_nodes", "group_by_section_membership", "group_by_scope"]),
        "ordering_strategy": enum_string(["active_node_order", "explicit_render_order", "canonical_body_alpha"]),
        "heading_style": enum_string(["none", "title_only", "numbered"]),
        "include_metadata_fields": string_array(min_items=0),
        "include_receipt_footer": boolean(),
        "redaction_policy_ref": id_string(),
        "render_order_ref": id_string(),
        "render_targets_ref": id_string(),
    }

    render_plan_spec = {
        "plan_id": id_string(),
        "scope_ref": id_string(),
        "profile_ref": id_string(),
        "current_state_view_ref": id_string(),
        "target_node_refs": string_array(pattern="^[A-Za-z0-9._:/-]+$", min_items=1),
        "output_path": nonempty_string(),
        "output_format": enum_string(["markdown", "yaml", "json"]),
        "target_projection_flag": enum_string(["machine_readable", "rendered_text", "exportable"]),
        "ordering_strategy": enum_string(["active_node_order", "explicit_render_order", "canonical_body_alpha"]),
        "section_strategy": enum_string(["linear_nodes", "group_by_section_membership", "group_by_scope"]),
        "render_order_ref": id_string(),
        "redaction_policy_ref": id_string(),
        "generated_from_ref": id_string(),
    }

    render_execution_receipt_spec = {
        "execution_receipt_id": id_string(),
        "plan_ref": id_string(),
        "profile_ref": id_string(),
        "target_view_ref": id_string(),
        "output_ref": nonempty_string(),
        "output_sha256": sha256_hex(),
        "rendered_node_count": integer_min(0),
        "rendered_projection_flag": enum_string(["machine_readable", "rendered_text", "exportable"]),
        "execution_status": enum_string(["success", "failed", "partial"]),
        "generated_at": datetime_string(),
        "cited_object_refs": string_array(pattern="^[A-Za-z0-9._:/-]+$", min_items=0),
        "drift_check_required": boolean(),
    }

    render_drift_receipt_spec = {
        "drift_receipt_id": id_string(),
        "plan_ref": id_string(),
        "target_view_ref": id_string(),
        "output_ref": nonempty_string(),
        "current_view_hash": nonempty_string(),
        "output_sha256": sha256_hex(),
        "drift_status": enum_string(["in_sync", "out_of_sync", "missing_output", "stale_view"]),
        "compared_at": datetime_string(),
        "blocker": boolean(),
        "recommended_route": enum_string(["render_refresh", "export_prep", "deferred"]),
    }

    defs[RENDER_PROFILE_KIND] = clone_with_new_spec(
        defs,
        "PRIME_CANON_FORMULA_PROFILE_V1",
        RENDER_PROFILE_KIND,
        "Cycle-2 frozen render profile object controlling rendered canon projection defaults.",
        render_profile_spec,
        [
            "profile_id",
            "default_output_format",
            "target_projection_flag",
            "section_strategy",
            "ordering_strategy",
            "heading_style",
            "include_metadata_fields",
            "include_receipt_footer",
            "redaction_policy_ref",
            "render_order_ref",
            "render_targets_ref",
        ],
    )

    defs[RENDER_PLAN_KIND] = clone_with_new_spec(
        defs,
        "PRIME_CANON_REPLAY_MANIFEST_V1",
        RENDER_PLAN_KIND,
        "Cycle-2 frozen render plan object binding a current-state view and render profile to one explicit projection output.",
        render_plan_spec,
        [
            "plan_id",
            "scope_ref",
            "profile_ref",
            "current_state_view_ref",
            "target_node_refs",
            "output_path",
            "output_format",
            "target_projection_flag",
            "ordering_strategy",
            "section_strategy",
            "render_order_ref",
            "redaction_policy_ref",
            "generated_from_ref",
        ],
    )

    defs[RENDER_EXECUTION_RECEIPT_KIND] = clone_with_new_spec(
        defs,
        "PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1",
        RENDER_EXECUTION_RECEIPT_KIND,
        "Cycle-2 frozen receipt proving one render-plan execution against one current-state view.",
        render_execution_receipt_spec,
        [
            "execution_receipt_id",
            "plan_ref",
            "profile_ref",
            "target_view_ref",
            "output_ref",
            "output_sha256",
            "rendered_node_count",
            "rendered_projection_flag",
            "execution_status",
            "generated_at",
            "cited_object_refs",
            "drift_check_required",
        ],
    )

    defs[RENDER_DRIFT_RECEIPT_KIND] = clone_with_new_spec(
        defs,
        "PRIME_CANON_REDUCTION_DECISION_RECEIPT_V1",
        RENDER_DRIFT_RECEIPT_KIND,
        "Cycle-2 frozen receipt proving whether a rendered output is still aligned to the current-state view it claims to project.",
        render_drift_receipt_spec,
        [
            "drift_receipt_id",
            "plan_ref",
            "target_view_ref",
            "output_ref",
            "current_view_hash",
            "output_sha256",
            "drift_status",
            "compared_at",
            "blocker",
            "recommended_route",
        ],
    )

    bundle_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    print("added defs:")
    print(RENDER_PROFILE_KIND)
    print(RENDER_PLAN_KIND)
    print(RENDER_EXECUTION_RECEIPT_KIND)
    print(RENDER_DRIFT_RECEIPT_KIND)

if __name__ == "__main__":
    main()
