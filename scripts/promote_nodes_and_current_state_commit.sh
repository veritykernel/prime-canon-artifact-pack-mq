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
if [ ! -f "receipts/immutable/$SUBJECT_SLUG/promotion-readiness-packet.yaml" ]; then
  echo "missing promotion readiness packet for $SUBJECT_SLUG" >&2
  exit 1
fi
if [ ! -f "receipts/immutable/$SUBJECT_SLUG/promotion-readiness-summary.yaml" ]; then
  echo "missing promotion readiness summary for $SUBJECT_SLUG" >&2
  exit 1
fi
if [ ! -f "replay/manifests/$SUBJECT_SLUG/promotion-readiness-replay.yaml" ]; then
  echo "missing promotion readiness replay manifest for $SUBJECT_SLUG" >&2
  exit 1
fi
python3 scripts/promote_nodes_and_current_state.py "$REPO" "$SUBJECT_SLUG"
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
rm -rf scripts/__pycache__
git add "scripts/promote_nodes_and_current_state.py" "scripts/promote_nodes_and_current_state_commit.sh" "canon/corpora/$SUBJECT_SLUG/index.yaml" "canon/nodes/$SUBJECT_SLUG" "views/current/$SUBJECT_SLUG.yaml" "receipts/immutable/$SUBJECT_SLUG"
git commit -m "promotion: first canon node and current state view pass for $SUBJECT_SLUG"
