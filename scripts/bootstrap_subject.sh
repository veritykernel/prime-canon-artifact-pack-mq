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
SUBJECT_TITLE="${2:-Subject 0001}"
INTAKE_SCOPE="${INTAKE_SCOPE:-Initial live subject bootstrap.}"
if [ -z "${SOURCE_REF_1:-}" ]; then export SOURCE_REF_1="pending://subject-0001/source-0001"; fi
if [ -z "${SOURCE_REF_2:-}" ]; then export SOURCE_REF_2="pending://subject-0001/source-0002"; fi
export SUBJECT_SLUG SUBJECT_TITLE INTAKE_SCOPE
python3 - <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import os
import yaml

repo = Path(".").resolve()
subject_slug = os.environ["SUBJECT_SLUG"].strip()
subject_title = os.environ["SUBJECT_TITLE"].strip()
intake_scope = os.environ["INTAKE_SCOPE"].strip()

source_refs = []
for key in sorted(os.environ):
    if key.startswith("SOURCE_REF_"):
        value = os.environ[key].strip()
        if value:
            source_refs.append(value)

if not subject_slug:
    raise SystemExit("SUBJECT_SLUG must not be empty")
if not subject_title:
    raise SystemExit("SUBJECT_TITLE must not be empty")
if not source_refs:
    raise SystemExit("At least one SOURCE_REF_* value is required")

template_index = repo / "canon/corpora/example-subject/index.yaml"
if not template_index.exists():
    raise SystemExit(f"Missing template index: {template_index}")

runtime_dirs = [
    f"canon/corpora/{subject_slug}",
    f"canon/source_units/{subject_slug}",
    f"canon/candidate_claims/{subject_slug}",
    f"canon/evidence_links/{subject_slug}",
    f"canon/contradictions/{subject_slug}",
    f"canon/supersession/{subject_slug}",
    f"canon/nodes/{subject_slug}",
    f"receipts/immutable/{subject_slug}",
    f"replay/manifests/{subject_slug}",
]

for rel in runtime_dirs:
    path = repo / rel
    path.mkdir(parents=True, exist_ok=True)
    if not rel.startswith("canon/corpora/"):
        (path / ".gitkeep").touch()

(repo / "views/rendered").mkdir(parents=True, exist_ok=True)

with template_index.open("r", encoding="utf-8") as fh:
    data = yaml.safe_load(fh)

def walk(x):
    if isinstance(x, dict):
        return {k: walk(v) for k, v in x.items()}
    if isinstance(x, list):
        return [walk(v) for v in x]
    if isinstance(x, str):
        return (
            x.replace("example-subject", subject_slug)
             .replace("Example subject", subject_title)
             .replace("Example Subject", subject_title)
        )
    return x

data = walk(data)
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

data.setdefault("metadata", {})
data.setdefault("attributes", {})
data.setdefault("spec", {})
data["attributes"].setdefault("identity", {})
data["attributes"].setdefault("lineage", {})
data["attributes"].setdefault("evidence", {})
data["attributes"].setdefault("governance", {})
data["attributes"].setdefault("operational", {})
data["attributes"].setdefault("temporal", {})

data["metadata"]["object_id"] = f"pc.corpus.{subject_slug}"
data["metadata"]["display_name"] = f"{subject_title} corpus index"
data["metadata"]["created_at"] = now
data["metadata"]["updated_at"] = now

data["attributes"]["identity"]["corpus_id"] = f"pc.corpus.{subject_slug}"
data["attributes"]["identity"]["subject_slug"] = subject_slug
data["attributes"]["identity"]["canonical_home"] = f"canon/corpora/{subject_slug}/index.yaml"

data["attributes"]["lineage"]["source_refs"] = source_refs
data["attributes"]["lineage"]["source_unit_refs"] = []
data["attributes"]["lineage"]["reduction_path"] = ["intake"]
data["attributes"]["lineage"]["derivation_receipt_refs"] = []

data["attributes"]["evidence"]["evidence_ref_count"] = len(source_refs)

data["attributes"]["governance"]["promotion_tier"] = "draft"

data["attributes"]["operational"]["lane_ref"] = "intake"
data["attributes"]["operational"]["repo_home"] = f"canon/corpora/{subject_slug}/index.yaml"
data["attributes"]["operational"]["route_destination"] = "reduction"

data["attributes"]["temporal"]["observed_at"] = now
data["attributes"]["temporal"]["reduced_at"] = now
data["attributes"]["temporal"]["status_since"] = now

data["spec"]["corpus_id"] = f"pc.corpus.{subject_slug}"
data["spec"]["subject_slug"] = subject_slug
data["spec"]["source_refs"] = source_refs
data["spec"]["source_count"] = len(source_refs)
data["spec"]["intake_scope"] = intake_scope
data["spec"]["status"] = "open"

out = repo / f"canon/corpora/{subject_slug}/index.yaml"
out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

(repo / f"views/rendered/{subject_slug}.md").write_text(
    f"# {subject_title}\n\nPending first promotion.\n",
    encoding="utf-8",
)
PY
python3 scripts/validate_pack.py .
