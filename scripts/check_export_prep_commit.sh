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
DRIFT_PATH="receipts/immutable/$SUBJECT_SLUG/render-drift.yaml"
if [ ! -f "$DRIFT_PATH" ]; then
  echo "missing required file: $DRIFT_PATH" >&2
  exit 1
fi
python3 scripts/check_export_prep.py "$REPO" "$SUBJECT_SLUG"
python3 scripts/validate_pack.py .
