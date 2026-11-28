#!/usr/bin/env python3
"""Read-only comparison against the view hash frozen by render execution."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import yaml

from promotion_preflight import PromotionRejected
from render_binding import compute_view_hash
from secure_projection_path import read_rendered, subject_name

SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def load_yaml(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise PromotionRejected(f"missing or linked yaml: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PromotionRejected(f"invalid yaml: {path}")
    return data


def check(repo: Path, subject: str) -> tuple[str, str]:
    subject = subject_name(subject)
    view = load_yaml(repo / "views" / "current" / f"{subject}.yaml")
    execution = load_yaml(repo / "receipts" / "immutable" / subject / "render-execution.yaml")
    view_spec = view["spec"]
    spec = execution["spec"]
    expected_ref = f"views/rendered/{subject}.md"
    if spec.get("output_ref") != expected_ref or spec.get("target_view_ref") != view_spec.get("view_id"):
        return "unbound_execution", "render_refresh"
    baseline = spec.get("render_view_hash")
    expected_sha = spec.get("output_sha256")
    if not isinstance(baseline, str) or not SHA256.fullmatch(baseline):
        return "unbound_execution", "render_refresh"
    if not isinstance(expected_sha, str) or not SHA256.fullmatch(expected_sha):
        return "unbound_execution", "render_refresh"
    try:
        raw = read_rendered(repo, subject)
    except (OSError, PromotionRejected):
        return "missing_output", "render_refresh"
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        return "out_of_sync", "render_refresh"
    try:
        current_view_hash = compute_view_hash(repo, subject, view)
    except (OSError, ValueError, KeyError, TypeError):
        return "stale_view", "render_refresh"
    if view_spec.get("view_hash") != baseline or current_view_hash != baseline:
        return "stale_view", "render_refresh"
    return "in_sync", "export_prep"


def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"
    status, route = check(repo, subject)
    blocked = status != "in_sync"
    print(f"drift_status={status}")
    print(f"blocker={str(blocked).lower()}")
    print(f"recommended_route={route}")
    if blocked:
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except (PromotionRejected, KeyError, TypeError, OSError) as exc:
        raise SystemExit(f"drift check rejected: {exc}") from exc
