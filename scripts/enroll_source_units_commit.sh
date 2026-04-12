#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
if [ ! -x .venv/bin/python3 ]; then
  ./scripts/bootstrap_python.sh
fi
source .venv/bin/activate
SUBJECT_SLUG="${1:-subject-0001}"
TSV_PATH="${2:-$REPO/work_orders/$SUBJECT_SLUG/source-units.tsv}"
if [ ! -f "$TSV_PATH" ]; then
  echo "missing TSV: $TSV_PATH" >&2
  exit 1
fi
ROW_COUNT="$(tail -n +2 "$TSV_PATH" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')"
if [ "$ROW_COUNT" = "0" ]; then
  echo "TSV has header only and no real source rows: $TSV_PATH" >&2
  exit 1
fi
python3 scripts/enroll_source_units.py "$REPO" "$SUBJECT_SLUG" "$TSV_PATH"
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
git add "canon/corpora/$SUBJECT_SLUG/index.yaml" "canon/source_units/$SUBJECT_SLUG"
git commit -m "intake: enroll first real source units for $SUBJECT_SLUG"
