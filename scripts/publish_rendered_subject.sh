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
SUBJECT_SLUG="$SUBJECT_SLUG" ./scripts/publish_guard.sh -- python3 scripts/publish_verified_subject.py "$REPO" "$SUBJECT_SLUG"
printf 'published_subject=%s\n' "$SUBJECT_SLUG"
