"""Verify frozen promotion inputs and an external human signature before writes.

The signer trust store is deliberately outside the repository. A checked-in
reviewer name or a compiler-generated readiness packet is not authorization.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SUBJECT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
PRINCIPAL = "human:reviewer"
NAMESPACE = "prime-canon-promotion-v1"
MAX_FILE = 2 * 1024 * 1024


class PromotionRejected(ValueError):
    pass


def _bytes(repo: Path, path: Path) -> bytes:
    if not path.resolve().is_relative_to(repo.resolve()):
        raise PromotionRejected(f"path escapes repository: {path}")
    if path.is_symlink():
        raise PromotionRejected(f"symlink input: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PromotionRejected(f"cannot read input {path}: {exc}") from exc
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
            raise PromotionRejected(f"input is not a bounded regular file: {path}")
        return stream.read(MAX_FILE + 1)


def _yaml(repo: Path, path: Path) -> tuple[dict, bytes]:
    raw = _bytes(repo, path)
    if len(raw) > MAX_FILE:
        raise PromotionRejected(f"oversized input: {path}")
    try:
        obj = yaml.safe_load(raw)
    except (yaml.YAMLError, UnicodeError) as exc:
        raise PromotionRejected(f"invalid YAML input: {path}") from exc
    if not isinstance(obj, dict):
        raise PromotionRejected(f"input is not an object: {path}")
    return obj, raw


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _external_file(path: Path, repo: Path, *, root_owned: bool) -> bytes:
    if path.is_symlink() or path.resolve().is_relative_to(repo.resolve()):
        raise PromotionRejected(f"approval material must be a regular file outside the repository: {path}")
    try:
        info = path.stat()
    except OSError as exc:
        raise PromotionRejected(f"missing approval material: {path}") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
        raise PromotionRejected(f"invalid approval material: {path}")
    if root_owned and (info.st_uid != 0 or info.st_mode & 0o022):
        raise PromotionRejected("allowed signers must be root-owned and not group/world writable")
    return path.read_bytes()


def verify_approval(repo: Path, approval_path: Path, signature_path: Path,
                    signers_path: Path, expected: dict, *, root_owned: bool = True) -> tuple[str, str]:
    """Return the trusted signer and signed-byte digest after checking scope."""
    raw = _external_file(approval_path, repo, root_owned=False)
    _external_file(signature_path, repo, root_owned=False)
    _external_file(signers_path, repo, root_owned=root_owned)
    try:
        approval = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise PromotionRejected("invalid approval JSON") from exc
    if not isinstance(approval, dict) or set(approval) != set(expected) | {"issued_at", "expires_at", "reviewer_principal"}:
        raise PromotionRejected("approval fields do not match the promotion contract")
    if any(approval.get(key) != value for key, value in expected.items()):
        raise PromotionRejected("approval does not bind these exact promotion inputs and targets")
    if approval["reviewer_principal"] != PRINCIPAL:
        raise PromotionRejected("approval has the wrong reviewer principal")
    try:
        issued = datetime.fromisoformat(approval["issued_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(approval["expires_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise PromotionRejected("invalid approval time") from exc
    now = datetime.now(timezone.utc)
    if issued.tzinfo is None or expires.tzinfo is None or issued > now or expires <= now or expires - issued > timedelta(days=30):
        raise PromotionRejected("approval is stale or has an invalid validity window")
    result = subprocess.run(
        ["ssh-keygen", "-Y", "verify", "-f", str(signers_path), "-I", PRINCIPAL,
         "-n", NAMESPACE, "-s", str(signature_path)],
        input=raw, capture_output=True, check=False, timeout=10,
    )
    if result.returncode != 0:
        raise PromotionRejected("human approval signature verification failed")
    return PRINCIPAL, _digest(raw)


def preflight(repo: Path, subject: str, *, approval_path: Path | None = None,
              signature_path: Path | None = None, signers_path: Path | None = None,
              root_owned: bool = True) -> dict:
    if not SUBJECT.fullmatch(subject):
        raise PromotionRejected("invalid subject slug")
    receipt_dir = repo / "receipts" / "immutable" / subject
    corpus, corpus_raw = _yaml(repo, repo / "canon" / "corpora" / subject / "index.yaml")
    packet, packet_raw = _yaml(repo, receipt_dir / "promotion-readiness-packet.yaml")
    summary, summary_raw = _yaml(repo, receipt_dir / "promotion-readiness-summary.yaml")
    manifest, manifest_raw = _yaml(repo, repo / "replay" / "manifests" / subject / "promotion-readiness-replay.yaml")
    formula_profile, formula_profile_raw = _yaml(repo, repo / "control" / "formulas" / "core-default.yaml")
    jurisdiction, jurisdiction_raw = _yaml(repo, repo / "control" / "jurisdictions" / "human-reviewer.yaml")
    corpus_id = corpus["spec"]["corpus_id"]
    if not isinstance(corpus_id, str) or not corpus_id.endswith(f".{subject}"):
        raise PromotionRejected("corpus identity does not match subject")
    for obj in (packet, summary, manifest):
        if obj["attributes"]["identity"]["corpus_id"] != corpus_id or obj["attributes"]["identity"]["subject_slug"] != subject:
            raise PromotionRejected("promotion object identity does not match corpus")
    if packet["spec"].get("ready") is not True or packet["spec"].get("blockers"):
        raise PromotionRejected("promotion readiness has not passed")
    targets = packet["spec"].get("target_refs")
    if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets):
        raise PromotionRejected("invalid promotion target set")
    if summary["spec"].get("target_ref") != packet["metadata"]["object_id"]:
        raise PromotionRejected("readiness summary refers to a different packet")
    if manifest["spec"].get("scope_ref") != corpus_id:
        raise PromotionRejected("replay manifest refers to a different corpus")

    objects: dict[str, tuple[dict, bytes, Path]] = {}
    groups = (
        (repo / "canon" / "candidate_claims" / subject, "claim-*.yaml"),
        (repo / "canon" / "evidence_links" / subject, "link-*.yaml"),
        (receipt_dir, "admissibility-*.yaml"),
        (receipt_dir, "formula-eval-*.yaml"),
        (receipt_dir, "topology-scout-summary.yaml"),
    )
    for directory, pattern in groups:
        for path in sorted(directory.glob(pattern)):
            obj, raw = _yaml(repo, path)
            object_id = obj["metadata"]["object_id"]
            if object_id in objects:
                raise PromotionRejected(f"duplicate input object id: {object_id}")
            if obj["attributes"]["identity"]["corpus_id"] != corpus_id or obj["attributes"]["identity"]["subject_slug"] != subject:
                raise PromotionRejected(f"input object identity mismatch: {path}")
            objects[object_id] = (obj, raw, path)
    declared = manifest["spec"].get("object_refs")
    hashes = manifest["spec"].get("input_hashes")
    if not isinstance(declared, list) or not isinstance(hashes, list) or len(set(declared)) != len(declared):
        raise PromotionRejected("invalid replay object list")
    hash_map = {entry["object_ref"]: entry["sha256"] for entry in hashes}
    if len(hash_map) != len(hashes) or set(declared) != set(objects) or set(hash_map) != set(objects):
        raise PromotionRejected("replay manifest does not cover the exact current input set")
    for object_id, (_, raw, _) in objects.items():
        if hash_map[object_id] != _digest(raw):
            raise PromotionRejected(f"replay hash mismatch: {object_id}")
    claims = {key: value for key, value in objects.items() if key.startswith("pc.candidate_claim.")}
    if set(targets) != set(claims):
        raise PromotionRejected("packet targets do not match frozen claims")
    links = {}
    for object_id, (obj, _, _) in objects.items():
        if object_id.startswith("pc.evidence_link."):
            claim_ref = obj["spec"]["claim_ref"]
            if claim_ref in links:
                raise PromotionRejected(f"duplicate evidence link for {claim_ref}")
            links[claim_ref] = obj
    if set(links) != set(targets):
        raise PromotionRejected("evidence links do not match frozen claims")
    for target in targets:
        claim = claims[target][0]
        if claim["spec"]["claim_id"] != target:
            raise PromotionRejected(f"claim id mismatch: {target}")

    if approval_path is None or signature_path is None or signers_path is None:
        raise PromotionRejected("external signed human approval and trusted signer store are required")
    expected = {
        "kind": "PRIME_CANON_PROMOTION_APPROVAL_V1",
        "subject_slug": subject,
        "corpus_id": corpus_id,
        "corpus_sha256": _digest(corpus_raw),
        "packet_sha256": _digest(packet_raw),
        "summary_sha256": _digest(summary_raw),
        "manifest_sha256": _digest(manifest_raw),
        "formula_profile_sha256": _digest(formula_profile_raw),
        "jurisdiction_sha256": _digest(jurisdiction_raw),
        "target_refs": targets,
    }
    reviewer, approval_hash = verify_approval(repo, approval_path, signature_path, signers_path,
                                               expected, root_owned=root_owned)
    policy = formula_profile["spec"]
    jurisdiction_spec = jurisdiction["spec"]
    hard_gates = {item["name"] for item in policy.get("hard_gates", []) if item.get("blocking") is True}
    required = {"admissibility_pass", "jurisdiction_pass", "no_open_critical_contradiction", "required_receipts_present"}
    if (policy.get("profile_id") != "pc.formula_profile.core-default"
            or not required.issubset(hard_gates)
            or jurisdiction_spec.get("actor_class") != "human"
            or jurisdiction_spec.get("actor_ref") != reviewer
            or "promote" not in jurisdiction_spec.get("allowed_actions", [])
            or "promote" in jurisdiction_spec.get("forbidden_actions", [])):
        raise PromotionRejected("configured formula or jurisdiction policy does not authorize promotion")
    max_age = policy.get("expiry_policy", {}).get("max_age_days")
    if not isinstance(max_age, int) or max_age < 1 or max_age > 30 or policy["expiry_policy"].get("expires_when_inputs_change") is not True:
        raise PromotionRejected("invalid formula expiry policy")
    now = datetime.now(timezone.utc)
    for obj in (packet, summary, manifest):
        try:
            created = datetime.fromisoformat(obj["metadata"]["created_at"].replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise PromotionRejected("invalid promotion object time") from exc
        if created.tzinfo is None or created > now or now - created > timedelta(days=max_age):
            raise PromotionRejected("promotion readiness evidence has expired")
    gate_results = {item["gate"]: item["status"] for item in packet["spec"].get("gate_results", [])}
    if gate_results.get("formula_eval_receipts_present") != "pass":
        raise PromotionRejected("formula evaluation gate has not passed")
    formulas = {}
    for object_id, (obj, _, _) in objects.items():
        if obj.get("kind") == "PRIME_CANON_FORMULA_EVAL_RECEIPT_V1":
            ref = obj["spec"]["target_ref"]
            if ref in formulas or obj["spec"].get("formula_profile_ref") != policy["profile_id"]:
                raise PromotionRejected("duplicate or wrong-profile formula evaluation")
            formulas[ref] = obj
    if set(formulas) != set(targets):
        raise PromotionRejected("missing formula evaluation for exact promotion targets")
    composites = {item["name"]: item for item in policy.get("composites", [])}
    try:
        promote_min = next(band["min"] for band in composites["inclusion_score"]["threshold_bands"]
                           if band["label"] == "promote_candidate")
        ready_min = next(band["min"] for band in composites["promotion_readiness_score"]["threshold_bands"]
                         if band["label"] == "ready")
        for ref in targets:
            snapshot = formulas[ref]["spec"]["input_snapshot"]
            metrics = formulas[ref]["spec"]["output_metrics"]
            inclusion = float(metrics["inclusion_score"])
            strength = float(metrics["evidence_strength"])
            diversity = min(1.0, float(snapshot["source_diversity"]) / 3.0)
            conflict = float(metrics["conflict_severity"])
            readiness = 0.35 * inclusion + 0.25 * (1.0 - conflict) + 0.20 * strength + 0.20 * diversity
            if (not all(math.isfinite(value) for value in (inclusion, strength, diversity, conflict, readiness))
                    or not 0 <= strength <= 1 or not 0 <= conflict <= 1
                    or inclusion < float(promote_min) or readiness < float(ready_min)):
                raise PromotionRejected(f"formula score gate has not passed for {ref}")
    except (KeyError, StopIteration, TypeError, ValueError) as exc:
        if isinstance(exc, PromotionRejected):
            raise
        raise PromotionRejected("formula evaluation or threshold bands are invalid") from exc
    decisions = {}
    for obj, _, _ in objects.values():
        if obj.get("kind") == "PRIME_CANON_ADMISSIBILITY_DECISION_V1":
            ref = obj["spec"]["target_claim_ref"]
            if ref in decisions:
                raise PromotionRejected("duplicate admissibility decision")
            decisions[ref] = obj
    if set(decisions) != set(targets) or any(decisions[ref]["spec"].get("pass_fail") != "pass" for ref in targets):
        raise PromotionRejected("admissibility hard gate has not passed")
    if any(obj["spec"].get("blocker_state") != "none" for obj, _, _ in objects.values()
           if obj.get("metadata", {}).get("object_id", "").endswith(".topology-scout")):
        raise PromotionRejected("topology contradiction gate has not passed")
    return {"corpus": corpus, "corpus_sha256": _digest(corpus_raw), "packet": packet, "summary": summary,
            "manifest": manifest, "claims": claims, "links": links,
            "reviewer": reviewer, "approval_sha256": approval_hash}
