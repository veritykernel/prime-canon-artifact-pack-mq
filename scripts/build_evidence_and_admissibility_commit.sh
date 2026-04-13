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
CLAIM_COUNT="$(find "canon/candidate_claims/$SUBJECT_SLUG" -type f -name 'claim-*.yaml' | wc -l | tr -d ' ')"
if [ "$CLAIM_COUNT" = "0" ]; then
  echo "no candidate claims found for $SUBJECT_SLUG" >&2
  exit 1
fi
python3 scripts/build_evidence_and_admissibility.py "$REPO" "$SUBJECT_SLUG"
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
git add "scripts/build_evidence_and_admissibility.py" "scripts/build_evidence_and_admissibility_commit.sh" "canon/corpora/$SUBJECT_SLUG/index.yaml" "canon/evidence_links/$SUBJECT_SLUG" "receipts/immutable/$SUBJECT_SLUG"
git commit -m "reduction: first evidence-link plus admissibility pass for $SUBJECT_SLUG"
