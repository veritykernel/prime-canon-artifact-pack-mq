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
CLAIM_COUNT="$(find "canon/candidate_claims/$SUBJECT_SLUG" -type f -name 'claim-*.yaml' | wc -l | tr -d ' ')"
ADMISS_COUNT="$(find "receipts/immutable/$SUBJECT_SLUG" -type f -name 'admissibility-*.yaml' | wc -l | tr -d ' ')"
if [ "$CLAIM_COUNT" = "0" ]; then
  echo "no candidate claims found for $SUBJECT_SLUG" >&2
  exit 1
fi
if [ "$ADMISS_COUNT" = "0" ]; then
  echo "no admissibility decisions found for $SUBJECT_SLUG" >&2
  exit 1
fi
python3 scripts/scout_contradictions_and_supersession.py "$REPO" "$SUBJECT_SLUG"
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
rm -rf scripts/__pycache__
git add "scripts/scout_contradictions_and_supersession.py" "scripts/scout_contradictions_and_supersession_commit.sh" "canon/corpora/$SUBJECT_SLUG/index.yaml" "canon/contradictions/$SUBJECT_SLUG" "canon/supersession/$SUBJECT_SLUG" "receipts/immutable/$SUBJECT_SLUG"
git commit -m "reduction: first contradiction plus supersession scout pass for $SUBJECT_SLUG"
