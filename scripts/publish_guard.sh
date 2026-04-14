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
SUBJECT_SLUG="${SUBJECT_SLUG:-subject-0001}"
if [ "${1:-}" = "--" ]; then
  shift
fi
if [ "$#" -eq 0 ]; then
  echo "usage: SUBJECT_SLUG=subject-0001 ./scripts/publish_guard.sh -- <publish-command> [args...]" >&2
  exit 64
fi
python3 scripts/check_export_prep.py "$REPO" "$SUBJECT_SLUG"
exec "$@"
