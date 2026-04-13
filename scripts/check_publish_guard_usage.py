#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()

ALLOWLIST = {
    "scripts/publish_guard.sh",
    "scripts/publish_guard_commit.sh",
    "scripts/publish_rendered_subject.sh",
    "scripts/publish_rendered_subject_commit.sh",
    "scripts/check_publish_guard_usage.py",
}

PUBLISH_PATTERNS = [
    r'\bcp\s+["' "'" r']?views/rendered/',
    r'\brsync\b.*views/rendered/',
    r'\bmv\s+["' "'" r']?views/rendered/',
    r'\bscp\b.*views/rendered/',
    r'/Users/Shared/nuum-work/stage/.*\.rendered\.md',
]

def is_suspicious_publish_script(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.MULTILINE) for pattern in PUBLISH_PATTERNS)

def main() -> None:
    bad = []
    for path in sorted((REPO / "scripts").rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(REPO))
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if is_suspicious_publish_script(text) and "publish_guard.sh" not in text:
            bad.append(rel)
    if bad:
        print("unguarded publish usage detected in repo-owned scripts:")
        for rel in bad:
            print(rel)
        raise SystemExit(1)
    print("publish guard usage check passed")

if __name__ == "__main__":
    main()
