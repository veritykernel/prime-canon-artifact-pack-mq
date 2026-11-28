#!/usr/bin/env python3
"""Publish exactly the rendered bytes verified against the frozen receipts."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from promotion_preflight import PromotionRejected, SUBJECT, _yaml
from render_binding import compute_view_hash
from secure_projection_path import DEFAULT_STAGE_ROOT, read_rendered, replace_regular, stage_directory


def publish(repo: Path, subject: str, *, stage_root: Path = DEFAULT_STAGE_ROOT) -> Path:
    repo = repo.resolve()
    if not SUBJECT.fullmatch(subject):
        raise PromotionRejected("invalid subject slug")
    cfg, _ = _yaml(repo, repo / "control" / "publish" / "publish-targets.default.yaml")
    view, _ = _yaml(repo, repo / "views" / "current" / f"{subject}.yaml")
    receipt_dir = repo / "receipts" / "immutable" / subject
    execution, _ = _yaml(repo, receipt_dir / "render-execution.yaml")
    drift, _ = _yaml(repo, receipt_dir / "render-drift.yaml")
    expected_ref = f"views/rendered/{subject}.md"
    spec = execution["spec"]
    drift_spec = drift["spec"]
    view_spec = view["spec"]
    try:
        actual_view_hash = compute_view_hash(repo, subject, view)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise PromotionRejected(f"current render inputs could not be verified: {exc}") from exc
    if (spec.get("output_ref") != expected_ref or drift_spec.get("output_ref") != expected_ref
            or spec.get("target_view_ref") != view_spec.get("view_id")
            or drift_spec.get("target_view_ref") != view_spec.get("view_id")
            or drift_spec.get("current_view_hash") != view_spec.get("view_hash")
            or spec.get("render_view_hash") != view_spec.get("view_hash")
            or actual_view_hash != view_spec.get("view_hash")
            or not isinstance(spec.get("render_view_hash"), str)
            or drift_spec.get("output_sha256") != spec.get("output_sha256")
            or drift_spec.get("drift_status") != "in_sync"
            or drift_spec.get("blocker") is not False
            or drift_spec.get("recommended_route") != "export_prep"):
        raise PromotionRejected("render receipts and current view do not authorize these exact bytes")
    raw = read_rendered(repo, subject)
    if hashlib.sha256(raw).hexdigest() != spec.get("output_sha256"):
        raise PromotionRejected("rendered source bytes differ from execution receipt")
    target_value = cfg.get("subjects", {}).get(subject, {}).get("rendered_markdown_path")
    if not isinstance(target_value, str) or not target_value:
        raise PromotionRejected("missing publish target")
    target = Path(target_value)
    expected_target = stage_root / f"{subject}.rendered.md"
    if target.parts != expected_target.parts or ".." in target.parts:
        raise PromotionRejected("publish target must be inside the trusted stage root")
    directory_fd = stage_directory(stage_root)
    try:
        replace_regular(directory_fd, target.name, raw)
    finally:
        os.close(directory_fd)
    return target


if __name__ == "__main__":
    try:
        destination = publish(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."),
                              sys.argv[2] if len(sys.argv) > 2 else "subject-0001")
    except (PromotionRejected, OSError) as exc:
        raise SystemExit(f"publication rejected: {exc}") from exc
    print(f"published_to={destination}")
