#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONDONTWRITEBYTECODE=1
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
rm -rf scripts/__pycache__
if [ ! -x .venv/bin/python3 ]; then
  ./scripts/bootstrap_python.sh
fi
source .venv/bin/activate
SUBJECT_SLUG="${1:-subject-0001}"
for f in \
  "canon/corpora/$SUBJECT_SLUG/index.yaml" \
  "views/current/$SUBJECT_SLUG.yaml" \
  "receipts/immutable/$SUBJECT_SLUG/render-execution.yaml" \
  "views/rendered/$SUBJECT_SLUG.md"
do
  if [ ! -f "$f" ]; then
    echo "missing required file: $f" >&2
    exit 1
  fi
done
python3 scripts/check_render_drift.py "$REPO" "$SUBJECT_SLUG"
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
rm -rf scripts/__pycache__
git add \
  scripts/check_render_drift.py \
  scripts/check_render_drift_commit.sh \
  "canon/corpora/$SUBJECT_SLUG/index.yaml" \
  "views/current/$SUBJECT_SLUG.yaml" \
  "receipts/immutable/$SUBJECT_SLUG/render-drift.yaml"
if ! git diff --cached --quiet; then
  git commit -m "projection: recompute render drift receipt for $SUBJECT_SLUG"
fi
BLOCKER="$(python3 - <<'PY'
from pathlib import Path
import yaml
p = Path("receipts/immutable/subject-0001/render-drift.yaml")
d = yaml.safe_load(p.read_text(encoding="utf-8"))
print("true" if d["spec"]["blocker"] else "false")
PY
)"
if [ "$BLOCKER" = "true" ]; then
  echo "render drift blocker=true; publication must fail closed" >&2
  exit 2
fi
