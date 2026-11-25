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
  echo "usage: SUBJECT_SLUG=subject-0001 ./scripts/publish_rendered_subject.sh subject-0001" >&2
  exit 64
fi
# The old arbitrary command mode allowed a green receipt to precede a copy
# that reopened different bytes. Only the publisher that hashes and copies
# one open snapshot is an admitted effect. /usr/bin/true is a dry-run check.
if ! { [ "$#" -eq 4 ] && [ "$1" = python3 ] && [ "$2" = scripts/publish_verified_subject.py ] && [ "$3" = "$REPO" ] && [ "$4" = "$SUBJECT_SLUG" ]; } \
   && ! { [ "$#" -eq 1 ] && [ "$1" = /usr/bin/true ]; }; then
  echo "publish guard accepts only the verified subject publisher" >&2
  exit 64
fi
python3 scripts/check_export_prep.py "$REPO" "$SUBJECT_SLUG"
exec "$@"
