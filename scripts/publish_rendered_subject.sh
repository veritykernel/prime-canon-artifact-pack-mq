#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONDONTWRITEBYTECODE=1
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
if [ ! -x .venv/bin/python3 ]; then
  ./scripts/bootstrap_python.sh
fi
source .venv/bin/activate
SUBJECT_SLUG="${1:-subject-0001}"
TARGET_PATH="$(python3 - "$REPO" "$SUBJECT_SLUG" <<'PY'
from pathlib import Path
import sys
import yaml
repo = Path(sys.argv[1])
subject_slug = sys.argv[2]
cfg = yaml.safe_load((repo / "control" / "publish" / "publish-targets.default.yaml").read_text(encoding="utf-8"))
subjects = cfg.get("subjects", {})
if subject_slug not in subjects:
    raise SystemExit(f"missing publish target for {subject_slug}")
target = subjects[subject_slug].get("rendered_markdown_path", "").strip()
if not target:
    raise SystemExit(f"missing rendered_markdown_path for {subject_slug}")
print(target)
PY
)"
SRC_PATH="views/rendered/$SUBJECT_SLUG.md"
if [ ! -f "$SRC_PATH" ]; then
  echo "missing rendered source: $SRC_PATH" >&2
  exit 1
fi
mkdir -p "$(dirname "$TARGET_PATH")"
SUBJECT_SLUG="$SUBJECT_SLUG" ./scripts/publish_guard.sh -- cp "$SRC_PATH" "$TARGET_PATH"
printf 'published_subject=%s\n' "$SUBJECT_SLUG"
printf 'published_to=%s\n' "$TARGET_PATH"
