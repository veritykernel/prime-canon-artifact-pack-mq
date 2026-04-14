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
python3 scripts/check_publish_guard_usage.py "$REPO"
SUBJECT_SLUG="$SUBJECT_SLUG" ./scripts/publish_guard.sh -- /usr/bin/true
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
rm -rf scripts/__pycache__
git add \
  control/publish/publish-targets.default.yaml \
  scripts/publish_rendered_subject.sh \
  scripts/check_publish_guard_usage.py \
  scripts/publish_rendered_subject_commit.sh
git commit -m "projection: bind repo-owned publish lane behind publish guard for $SUBJECT_SLUG"
