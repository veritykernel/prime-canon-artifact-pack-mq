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
if [ ! -f "views/current/$SUBJECT_SLUG.yaml" ]; then
  echo "missing current state view for $SUBJECT_SLUG" >&2
  exit 1
fi
NODE_COUNT="$(find "canon/nodes/$SUBJECT_SLUG" -type f -name 'node-*.yaml' | wc -l | tr -d ' ')"
if [ "$NODE_COUNT" = "0" ]; then
  echo "no canon nodes found for $SUBJECT_SLUG" >&2
  exit 1
fi
for f in \
  control/render/render-profile.default.yaml \
  control/render/render-order.default.yaml \
  control/render/render-targets.default.yaml \
  control/render/render-redaction.default.yaml
do
  if [ ! -f "$f" ]; then
    echo "missing render control surface: $f" >&2
    exit 1
  fi
done
rm -f "receipts/immutable/$SUBJECT_SLUG/rendered-projection-summary.yaml"
python3 scripts/build_rendered_projection.py "$REPO" "$SUBJECT_SLUG"
python3 scripts/validate_pack.py .
git diff --exit-code -- control schemas
rm -rf scripts/__pycache__
git add -A \
  scripts/build_rendered_projection.py \
  scripts/build_rendered_projection_commit.sh \
  canon/corpora/$SUBJECT_SLUG/index.yaml \
  canon/nodes/$SUBJECT_SLUG \
  views/current/$SUBJECT_SLUG.yaml \
  views/rendered/$SUBJECT_SLUG.md \
  receipts/immutable/$SUBJECT_SLUG
git commit -m "projection: make rendered projection lane control-driven with execution and drift receipts for $SUBJECT_SLUG"
