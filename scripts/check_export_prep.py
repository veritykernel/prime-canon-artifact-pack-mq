#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from check_render_drift import check

def load_yaml(path: Path):
    if not path.exists():
        raise SystemExit(f"missing yaml: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    drift_path = repo / "receipts" / "immutable" / subject_slug / "render-drift.yaml"
    drift = load_yaml(drift_path)
    execution = load_yaml(repo / "receipts" / "immutable" / subject_slug / "render-execution.yaml")
    view = load_yaml(repo / "views" / "current" / f"{subject_slug}.yaml")

    drift_status = drift["spec"]["drift_status"]
    blocker = bool(drift["spec"]["blocker"])
    recommended_route = drift["spec"]["recommended_route"]
    live_status, live_route = check(repo, subject_slug)

    ok = (
        drift_status == "in_sync"
        and blocker is False
        and recommended_route == "export_prep"
        and live_status == "in_sync"
        and live_route == "export_prep"
        and drift["spec"].get("current_view_hash") == execution["spec"].get("render_view_hash")
        and drift["spec"].get("current_view_hash") == view["spec"].get("view_hash")
        and drift["spec"].get("output_sha256") == execution["spec"].get("output_sha256")
        and drift["spec"].get("output_ref") == f"views/rendered/{subject_slug}.md"
        and drift["spec"].get("target_view_ref") == view["spec"].get("view_id")
    )

    print(f"drift_status={drift_status}")
    print(f"blocker={'true' if blocker else 'false'}")
    print(f"recommended_route={recommended_route}")
    print(f"live_drift_status={live_status}")
    print(f"export_prep_ready={'true' if ok else 'false'}")

    if not ok:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
