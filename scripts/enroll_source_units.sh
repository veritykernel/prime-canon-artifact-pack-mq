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
python3 scripts/enroll_source_units.py "$REPO" "$SUBJECT_SLUG" "$TSV_PATH"
python3 scripts/validate_pack.py .
