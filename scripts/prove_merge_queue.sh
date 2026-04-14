#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
if command -v fnm >/dev/null 2>&1; then eval "$(fnm env --use-on-cd 2>/dev/null || fnm env 2>/dev/null)"; fi
export PYTHONDONTWRITEBYTECODE=1
export GH_PROMPT_DISABLED=1
export GIT_PAGER=cat

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

ORG_SLUG="${ORG_SLUG:-veritykernel}"
SOURCE_BRANCH="${SOURCE_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d%H%M%S)}"
REPO_NAME="${REPO_NAME:-prime-canon-artifact-pack-mq-$RUN_ID}"
MQ_REPO="${MQ_REPO:-$ORG_SLUG/$REPO_NAME}"
WORKFLOW_FILE="publish-guard-check.yml"
WORKFLOW_NAME="publish-guard-check"
PROOF_BRANCH="mq-proof-$RUN_ID"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

cleanup() {
  git checkout "$CURRENT_BRANCH" >/dev/null 2>&1 || true
  if git show-ref --verify --quiet "refs/heads/$PROOF_BRANCH"; then
    git branch -D "$PROOF_BRANCH" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

gh auth status

if ! gh repo view "$MQ_REPO" >/dev/null 2>&1; then
  gh api --method POST "orgs/$ORG_SLUG/repos" -f name="$REPO_NAME" -F private=false >/dev/null
fi

if git remote get-url mq >/dev/null 2>&1; then
  git remote set-url mq "https://github.com/$MQ_REPO.git"
else
  git remote add mq "https://github.com/$MQ_REPO.git"
fi

git push -u mq "$SOURCE_BRANCH:main"
gh api --method PATCH "repos/$MQ_REPO" -f default_branch=main >/dev/null

git checkout -B "$PROOF_BRANCH" "$SOURCE_BRANCH"
git commit --allow-empty -m "mq proof trigger $RUN_ID"
PR_HEAD_SHA="$(git rev-parse HEAD)"
git push -u mq "$PROOF_BRANCH"

STATUS=""
CONCLUSION=""
for _ in $(seq 1 36); do
  RUN_JSON="$(gh run list --repo "$MQ_REPO" --workflow "$WORKFLOW_FILE" --branch "$PROOF_BRANCH" --event push --json status,conclusion,headSha --limit 20 2>/dev/null || echo '[]')"
  STATUS="$(python3 - <<'PY' "$RUN_JSON" "$PR_HEAD_SHA"
import json, sys
runs = json.loads(sys.argv[1])
head = sys.argv[2]
found = next((r for r in runs if r.get("headSha")==head), None)
print(found.get("status","") if found else "")
PY
)"
  CONCLUSION="$(python3 - <<'PY' "$RUN_JSON" "$PR_HEAD_SHA"
import json, sys
runs = json.loads(sys.argv[1])
head = sys.argv[2]
found = next((r for r in runs if r.get("headSha")==head), None)
print(found.get("conclusion","") if found else "")
PY
)"
  echo "proof-branch push $WORKFLOW_NAME status=${STATUS:-none} conclusion=${CONCLUSION:-none}"
  if [ "$STATUS" = "completed" ]; then
    break
  fi
  sleep 5
done

if [ "$STATUS" != "completed" ] || [ "$CONCLUSION" != "success" ]; then
  echo "$WORKFLOW_NAME did not complete successfully on proof-branch push in $MQ_REPO" >&2
  exit 1
fi

cat > /tmp/prime_canon_merge_queue_ruleset.json <<'JSON'
{
  "name": "required-ci-publish-guard-main-mq",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "required_status_checks",
      "parameters": {
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          {
            "context": "publish-guard-check"
          }
        ],
        "strict_required_status_checks_policy": true
      }
    },
    {
      "type": "merge_queue",
      "parameters": {
        "check_response_timeout_minutes": 30,
        "grouping_strategy": "HEADGREEN",
        "max_entries_to_build": 1,
        "max_entries_to_merge": 1,
        "merge_method": "SQUASH",
        "min_entries_to_merge": 1,
        "min_entries_to_merge_wait_minutes": 0
      }
    }
  ]
}
JSON

RULESET_ID="$(gh api "repos/$MQ_REPO/rulesets" --jq '.[] | select(.name=="required-ci-publish-guard-main-mq") | .id' 2>/dev/null | head -n1 || true)"

if [ -n "${RULESET_ID:-}" ]; then
  gh api --method PUT -H "Accept: application/vnd.github+json" "repos/$MQ_REPO/rulesets/$RULESET_ID" --input /tmp/prime_canon_merge_queue_ruleset.json >/dev/null
else
  gh api --method POST -H "Accept: application/vnd.github+json" "repos/$MQ_REPO/rulesets" --input /tmp/prime_canon_merge_queue_ruleset.json >/dev/null
fi

gh pr create --repo "$MQ_REPO" --base main --head "$PROOF_BRANCH" --title "mq proof $RUN_ID" --body "Deterministic merge queue proof for publish-guard-check." >/dev/null

PR_JSON="$(gh pr view --repo "$MQ_REPO" "$PROOF_BRANCH" --json number,url,headRefOid)"
export PR_JSON
PR_NUMBER="$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["PR_JSON"])["number"])
PY
)"
PR_URL="$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["PR_JSON"])["url"])
PY
)"
PR_HEAD_SHA="$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["PR_JSON"])["headRefOid"])
PY
)"

echo "org_slug=$ORG_SLUG"
echo "mq_repo=$MQ_REPO"
echo "pr_number=$PR_NUMBER"
echo "pr_url=$PR_URL"

STATUS=""
CONCLUSION=""
for _ in $(seq 1 36); do
  RUN_JSON="$(gh run list --repo "$MQ_REPO" --workflow "$WORKFLOW_FILE" --branch "$PROOF_BRANCH" --event pull_request --json status,conclusion,headSha,url --limit 20 2>/dev/null || echo '[]')"
  STATUS="$(python3 - <<'PY' "$RUN_JSON" "$PR_HEAD_SHA"
import json, sys
runs = json.loads(sys.argv[1])
head = sys.argv[2]
found = next((r for r in runs if r.get("headSha")==head), None)
print(found.get("status","") if found else "")
PY
)"
  CONCLUSION="$(python3 - <<'PY' "$RUN_JSON" "$PR_HEAD_SHA"
import json, sys
runs = json.loads(sys.argv[1])
head = sys.argv[2]
found = next((r for r in runs if r.get("headSha")==head), None)
print(found.get("conclusion","") if found else "")
PY
)"
  echo "pr $WORKFLOW_NAME status=${STATUS:-none} conclusion=${CONCLUSION:-none}"
  if [ "$STATUS" = "completed" ]; then
    break
  fi
  sleep 5
done

if [ "$STATUS" != "completed" ] || [ "$CONCLUSION" != "success" ]; then
  echo "$WORKFLOW_NAME did not complete successfully on pull_request for PR #$PR_NUMBER" >&2
  exit 1
fi

gh pr merge --repo "$MQ_REPO" "$PROOF_BRANCH" --squash --match-head-commit "$PR_HEAD_SHA"

STATUS=""
CONCLUSION=""
RUN_URL=""
for _ in $(seq 1 48); do
  RUN_JSON="$(gh run list --repo "$MQ_REPO" --workflow "$WORKFLOW_FILE" --event merge_group --json status,conclusion,url,displayTitle --limit 20 2>/dev/null || echo '[]')"
  STATUS="$(python3 - <<'PY' "$RUN_JSON"
import json, sys
runs = json.loads(sys.argv[1])
print(runs[0].get("status","") if runs else "")
PY
)"
  CONCLUSION="$(python3 - <<'PY' "$RUN_JSON"
import json, sys
runs = json.loads(sys.argv[1])
print(runs[0].get("conclusion","") if runs else "")
PY
)"
  RUN_URL="$(python3 - <<'PY' "$RUN_JSON"
import json, sys
runs = json.loads(sys.argv[1])
print(runs[0].get("url","") if runs else "")
PY
)"
  echo "merge_group $WORKFLOW_NAME status=${STATUS:-none} conclusion=${CONCLUSION:-none}"
  if [ "$STATUS" = "completed" ]; then
    break
  fi
  sleep 5
done

if [ "$STATUS" != "completed" ] || [ "$CONCLUSION" != "success" ]; then
  echo "merge_group $WORKFLOW_NAME did not complete successfully in $MQ_REPO" >&2
  echo "run_url=${RUN_URL:-none}" >&2
  exit 1
fi

echo "merge_queue_proof=success"
echo "repo=$MQ_REPO"
echo "pr_number=$PR_NUMBER"
echo "pr_url=$PR_URL"
echo "merge_group_run_url=$RUN_URL"
