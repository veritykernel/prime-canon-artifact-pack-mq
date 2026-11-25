from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from promotion_preflight import PromotionRejected, preflight
import promote_nodes_and_current_state
from publish_verified_subject import publish


SOURCE = Path(__file__).resolve().parents[2]
SUBJECT = "subject-0001"


class PromotionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        for directory in ("canon", "receipts", "replay", "schemas", "control"):
            shutil.copytree(SOURCE / directory, self.repo / directory)
        self.approval = self.root / "approval.json"
        self.signers = self.root / "allowed_signers"
        self.private = self.root / "reviewer_key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.private)],
                       check=True, capture_output=True)
        self.signers.write_text("human:reviewer " + self.private.with_suffix(".pub").read_text())
        self.sign()

    def sign(self):
        receipt = self.repo / "receipts" / "immutable" / SUBJECT
        paths = {
            "packet_sha256": receipt / "promotion-readiness-packet.yaml",
            "summary_sha256": receipt / "promotion-readiness-summary.yaml",
            "manifest_sha256": self.repo / "replay" / "manifests" / SUBJECT / "promotion-readiness-replay.yaml",
            "formula_profile_sha256": self.repo / "control" / "formulas" / "core-default.yaml",
            "jurisdiction_sha256": self.repo / "control" / "jurisdictions" / "human-reviewer.yaml",
        }
        packet = yaml.safe_load(paths["packet_sha256"].read_bytes())
        now = datetime.now(timezone.utc)
        body = {
            "kind": "PRIME_CANON_PROMOTION_APPROVAL_V1",
            "subject_slug": SUBJECT,
            "corpus_id": f"pc.corpus.{SUBJECT}",
            "corpus_sha256": hashlib.sha256((self.repo / "canon" / "corpora" / SUBJECT / "index.yaml").read_bytes()).hexdigest(),
            "target_refs": packet["spec"]["target_refs"],
            "issued_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(days=1)).isoformat(),
            "reviewer_principal": "human:reviewer",
        }
        body.update({name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()})
        self.approval.write_text(json.dumps(body, sort_keys=True))
        self.root.joinpath("approval.json.sig").unlink(missing_ok=True)
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(self.private),
                        "-n", "prime-canon-promotion-v1", str(self.approval)],
                       check=True, capture_output=True)

    def make_policy_ready(self):
        receipt_dir = self.repo / "receipts" / "immutable" / SUBJECT
        packet_path = receipt_dir / "promotion-readiness-packet.yaml"
        summary_path = receipt_dir / "promotion-readiness-summary.yaml"
        manifest_path = self.repo / "replay" / "manifests" / SUBJECT / "promotion-readiness-replay.yaml"
        packet = yaml.safe_load(packet_path.read_text())
        summary = yaml.safe_load(summary_path.read_text())
        manifest = yaml.safe_load(manifest_path.read_text())
        example = yaml.safe_load((SOURCE / "receipts" / "immutable" / "example-subject" / "formula-eval-receipt-0001.yaml").read_text())
        now = datetime.now(timezone.utc).isoformat()
        for ref in packet["spec"]["target_refs"]:
            seq = ref.rsplit(".", 1)[-1]
            path = receipt_dir / f"formula-eval-{seq}.yaml"
            formula = json.loads(json.dumps(example))
            object_id = f"pc.receipt.formula.{SUBJECT}.{seq}"
            formula["metadata"]["object_id"] = object_id
            formula["metadata"]["created_at"] = now
            formula["attributes"]["identity"] = {
                "corpus_id": f"pc.corpus.{SUBJECT}", "subject_slug": SUBJECT,
                "canonical_home": f"receipts/immutable/{SUBJECT}/formula-eval-{seq}.yaml",
            }
            formula["spec"]["receipt_id"] = object_id
            formula["spec"]["target_ref"] = ref
            formula["spec"]["input_snapshot"]["source_diversity"] = 3
            formula["spec"]["output_metrics"].update(
                inclusion_score=0.95, evidence_strength=1.0, conflict_severity=0.0)
            path.write_text(yaml.safe_dump(formula, sort_keys=False))
            manifest["spec"]["object_refs"].append(object_id)
            manifest["spec"]["input_hashes"].append({
                "object_ref": object_id, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest["spec"]["object_refs"].sort()
        manifest["spec"]["input_hashes"].sort(key=lambda item: item["object_ref"])
        packet["spec"]["required_gates"].append("formula_eval_receipts_present")
        packet["spec"]["gate_results"].append({
            "gate": "formula_eval_receipts_present", "status": "pass",
            "evidence": [entry["object_ref"] for entry in manifest["spec"]["input_hashes"]
            if entry["object_ref"].startswith("pc.receipt.formula.")]})
        for obj, path in ((packet, packet_path), (summary, summary_path), (manifest, manifest_path)):
            obj["metadata"]["created_at"] = now
            path.write_text(yaml.safe_dump(obj, sort_keys=False))

    def check(self):
        return preflight(self.repo, SUBJECT, approval_path=self.approval,
                         signature_path=self.root / "approval.json.sig",
                         signers_path=self.signers, root_owned=False)

    def test_valid_signature_and_frozen_inputs(self):
        self.make_policy_ready()
        self.sign()
        frozen = self.check()
        self.assertEqual(frozen["reviewer"], "human:reviewer")
        self.assertEqual(len(frozen["claims"]), 5)

    def test_signed_new_subject_writes_reviewer_bound_receipts(self):
        self.make_policy_ready()
        self.sign()
        receipt_dir = self.repo / "receipts" / "immutable" / SUBJECT
        for path in receipt_dir.glob("promotion-node-*.yaml"):
            path.unlink()
        (receipt_dir / "promotion-lane-summary.yaml").unlink()
        for path in (self.repo / "canon" / "nodes" / SUBJECT).glob("node-*.yaml"):
            path.unlink()
        verified = self.check()
        with patch.object(promote_nodes_and_current_state, "preflight", return_value=verified), \
             patch.object(sys, "argv", ["promote", str(self.repo), SUBJECT]):
            promote_nodes_and_current_state.main()
        summary = yaml.safe_load((receipt_dir / "promotion-lane-summary.yaml").read_text())
        self.assertEqual(summary["spec"]["reviewer_refs"], ["human:reviewer"])
        self.assertIn(verified["approval_sha256"], summary["spec"]["rationale"])
        self.assertTrue((self.repo / "views" / "current" / f"{SUBJECT}.yaml").exists())

    def test_changed_claim_fails_before_promotion(self):
        claim = self.repo / "canon" / "candidate_claims" / SUBJECT / "claim-0001.yaml"
        claim.write_text(claim.read_text() + "\n# changed after readiness\n")
        with self.assertRaisesRegex(PromotionRejected, "replay hash mismatch"):
            self.check()

    def test_unsigned_approval_change_fails(self):
        body = json.loads(self.approval.read_text())
        body["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        self.approval.write_text(json.dumps(body, sort_keys=True))
        with self.assertRaisesRegex(PromotionRejected, "signature verification failed"):
            self.check()

    def test_no_approval_fails_closed(self):
        with self.assertRaisesRegex(PromotionRejected, "external signed human approval"):
            preflight(self.repo, SUBJECT)

    def test_signed_historical_readiness_has_expired(self):
        with self.assertRaisesRegex(PromotionRejected, "evidence has expired"):
            self.check()

    def test_readiness_builder_blocks_missing_formula_receipts(self):
        receipt_dir = self.repo / "receipts" / "immutable" / SUBJECT
        (receipt_dir / "promotion-readiness-packet.yaml").unlink()
        (receipt_dir / "promotion-readiness-summary.yaml").unlink()
        (self.repo / "replay" / "manifests" / SUBJECT / "promotion-readiness-replay.yaml").unlink()
        result = subprocess.run([sys.executable, str(SOURCE / "scripts" / "build_promotion_readiness.py"),
                                 str(self.repo), SUBJECT], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = yaml.safe_load((self.repo / "receipts" / "immutable" / SUBJECT /
                                 "promotion-readiness-packet.yaml").read_text())
        self.assertFalse(packet["spec"]["ready"])
        self.assertIn("formula_eval_receipts_present", packet["spec"]["blockers"])

    def test_duplicate_claim_id_cannot_reuse_another_claims_decision(self):
        claim_dir = self.repo / "canon" / "candidate_claims" / SUBJECT
        first = yaml.safe_load((claim_dir / "claim-0001.yaml").read_text())
        second_path = claim_dir / "claim-0002.yaml"
        second = yaml.safe_load(second_path.read_text())
        second["spec"]["claim_id"] = first["spec"]["claim_id"]
        second_path.write_text(yaml.safe_dump(second, sort_keys=False))
        receipt_dir = self.repo / "receipts" / "immutable" / SUBJECT
        (receipt_dir / "promotion-readiness-packet.yaml").unlink()
        (receipt_dir / "promotion-readiness-summary.yaml").unlink()
        manifest_path = self.repo / "replay" / "manifests" / SUBJECT / "promotion-readiness-replay.yaml"
        manifest_path.unlink()
        result = subprocess.run([sys.executable, str(SOURCE / "scripts" / "build_promotion_readiness.py"),
                                 str(self.repo), SUBJECT], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate claim id", result.stderr)
        self.assertFalse(manifest_path.exists())

    def test_contributor_labels_cannot_create_passing_admissibility(self):
        for path in (self.repo / "canon" / "evidence_links" / SUBJECT).glob("link-*.yaml"):
            path.unlink()
        for path in (self.repo / "receipts" / "immutable" / SUBJECT).glob("admissibility-*.yaml"):
            path.unlink()
        result = subprocess.run([sys.executable, str(SOURCE / "scripts" / "build_evidence_and_admissibility.py"),
                                 str(self.repo), SUBJECT], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        decisions = list((self.repo / "receipts" / "immutable" / SUBJECT).glob("admissibility-*.yaml"))
        self.assertEqual(len(decisions), 5)
        for path in decisions:
            decision = yaml.safe_load(path.read_text())
            self.assertEqual(decision["spec"]["pass_fail"], "fail")
            self.assertIn("independent_source_verification", decision["spec"]["unmet_burdens"])
        for path in (self.repo / "canon" / "evidence_links" / SUBJECT).glob("link-*.yaml"):
            link = yaml.safe_load(path.read_text())
            self.assertEqual(link["spec"]["source_trust_class"], "unrated")
            self.assertEqual(link["spec"]["admissibility_weight"], 0.0)


class VerifiedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        for directory in ("control", "receipts", "views"):
            shutil.copytree(SOURCE / directory, self.repo / directory)
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.target = self.stage / f"{SUBJECT}.rendered.md"
        cfg_path = self.repo / "control" / "publish" / "publish-targets.default.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        cfg["subjects"][SUBJECT]["rendered_markdown_path"] = str(self.target)
        cfg_path.write_text(yaml.safe_dump(cfg))

    def test_publishes_the_verified_bytes(self):
        self.assertEqual(publish(self.repo, SUBJECT), self.target)
        self.assertEqual(self.target.read_bytes(), (self.repo / "views" / "rendered" / f"{SUBJECT}.md").read_bytes())

    def test_changed_render_cannot_replace_existing_publication(self):
        self.target.write_text("prior publication")
        source = self.repo / "views" / "rendered" / f"{SUBJECT}.md"
        source.write_text(source.read_text() + "\nchanged after drift check\n")
        with self.assertRaisesRegex(PromotionRejected, "rendered source bytes differ"):
            publish(self.repo, SUBJECT)
        self.assertEqual(self.target.read_text(), "prior publication")

    def test_symlink_target_cannot_overwrite_operator_file(self):
        protected = self.root / "operator-file"
        protected.write_text("keep")
        self.target.symlink_to(protected)
        with self.assertRaisesRegex(PromotionRejected, "target is a symlink"):
            publish(self.repo, SUBJECT)
        self.assertEqual(protected.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
