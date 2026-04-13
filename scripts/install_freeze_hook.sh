#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
mkdir -p .git/hooks
cat > .git/hooks/pre-commit <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
case "$BRANCH" in
  cycle-2/*)
    exit 0
    ;;
esac
if ! git diff --cached --quiet -- control schemas; then
  echo
  echo "ERROR: control/ and schemas/ are frozen for the first implementation cycle."
  git diff --cached --stat -- control schemas || true
  echo
  exit 1
fi
HOOK
chmod +x .git/hooks/pre-commit
echo "installed branch-aware .git/hooks/pre-commit freeze guard"
