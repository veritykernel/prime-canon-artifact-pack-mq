#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml

def load_yaml(path: Path):
    if not path.exists():
        raise SystemExit(f"missing yaml: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    subject_slug = sys.argv[2] if len(sys.argv) > 2 else "subject-0001"

    drift_path = repo / "receipts" / "immutable" / subject_slug / "render-drift.yaml"
    drift = load_yaml(drift_path)

    drift_status = drift["spec"]["drift_status"]
    blocker = bool(drift["spec"]["blocker"])
    recommended_route = drift["spec"]["recommended_route"]

    ok = (
        drift_status == "in_sync"
        and blocker is False
        and recommended_route == "export_prep"
    )

    print(f"drift_status={drift_status}")
    print(f"blocker={'true' if blocker else 'false'}")
    print(f"recommended_route={recommended_route}")
    print(f"export_prep_ready={'true' if ok else 'false'}")

    if not ok:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
