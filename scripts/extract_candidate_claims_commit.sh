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
SOURCE_COUNT="$(find "canon/source_units/$SUBJECT_SLUG" -type f -name 'unit-*.yaml' | wc -l | tr -d ' ')"
if [ "$SOURCE_COUNT" = "0" ]; then
  echo "no source units found for $SUBJECT_SLUG" >&2
  exit 1
fi
python3 scripts/extract_candidate_claims.py "$REPO" "$SUBJECT_SLUG"
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
git add "scripts/extract_candidate_claims.py" "scripts/extract_candidate_claims_commit.sh" "canon/corpora/$SUBJECT_SLUG/index.yaml" "canon/candidate_claims/$SUBJECT_SLUG"
git commit -m "reduction: first candidate_claim extraction pass for $SUBJECT_SLUG"
