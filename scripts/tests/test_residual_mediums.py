from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enroll_source_units import (MAX_NORMALIZED_TEXT_BYTES, MAX_SOURCE_ROWS,
                                 MAX_TOTAL_TEXT_BYTES, REQUIRED_COLUMNS, load_tsv)


SOURCE = Path(__file__).resolve().parents[2]
SUBJECT = "subject-0001"


class ResidualMediumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        for directory in ("canon", "receipts", "views", "schemas", "control", "work_orders"):
            shutil.copytree(SOURCE / directory, self.repo / directory)

    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SOURCE / "scripts" / name), str(self.repo),
                               SUBJECT, *args], capture_output=True, text=True)

    def test_rendered_output_symlink_rejected_before_other_writes(self):
        output = self.repo / "views" / "rendered" / f"{SUBJECT}.md"
        sentinel = self.root / "outside.md"
        sentinel.write_text("KEEP")
        output.unlink()
        output.symlink_to(sentinel)
        corpus = self.repo / "canon" / "corpora" / SUBJECT / "index.yaml"
        original_corpus = corpus.read_bytes()
        result = self.run_script("build_rendered_projection.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe rendered output destination", result.stderr)
        self.assertEqual(sentinel.read_text(), "KEEP")
        self.assertEqual(corpus.read_bytes(), original_corpus)

    def test_rendered_parent_symlink_rejected(self):
        output_dir = self.repo / "views" / "rendered"
        shutil.rmtree(output_dir)
        outside = self.root / "outside"
        outside.mkdir()
        output_dir.symlink_to(outside, target_is_directory=True)
        result = self.run_script("build_rendered_projection.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe rendered output directory", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_regular_rendered_output_still_builds(self):
        result = self.run_script("build_rendered_projection.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.repo / "views" / "rendered" / f"{SUBJECT}.md"
        self.assertTrue(output.is_file())
        self.assertIn(f"# {SUBJECT} rendered canon", output.read_text())
        receipt = yaml.safe_load((self.repo / "receipts" / "immutable" / SUBJECT /
                                  "render-execution.yaml").read_text())
        self.assertIn(hashlib.sha256(output.read_bytes()).hexdigest(), str(receipt))

    def write_tsv(self, bodies: list[str]) -> Path:
        path = self.root / "input.tsv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=REQUIRED_COLUMNS, delimiter="\t")
            writer.writeheader()
            for index, body in enumerate(bodies, start=1):
                writer.writerow({"seq": index, "source_ref": "source://fixture", "locator": f"span-{index}",
                                 "start": 0, "end": 1, "observed_at": "2026-11-25T00:00:00Z",
                                 "scope": "fixture", "normalized_text": body})
        return path

    def test_source_row_quota_rejects_before_enrollment_writes(self):
        path = self.write_tsv(["x"] * (MAX_SOURCE_ROWS + 1))
        corpus = self.repo / "canon" / "corpora" / SUBJECT / "index.yaml"
        original_corpus = corpus.read_bytes()
        result = self.run_script("enroll_source_units.py", str(path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source rows", result.stderr)
        self.assertEqual(corpus.read_bytes(), original_corpus)

    def test_source_body_and_aggregate_quota(self):
        with self.assertRaisesRegex(SystemExit, "normalized_text exceeds"):
            load_tsv(self.write_tsv(["x" * (MAX_NORMALIZED_TEXT_BYTES + 1)]))
        bodies = ["x" * MAX_NORMALIZED_TEXT_BYTES] * (MAX_TOTAL_TEXT_BYTES // MAX_NORMALIZED_TEXT_BYTES + 1)
        with self.assertRaisesRegex(SystemExit, "aggregate bytes"):
            load_tsv(self.write_tsv(bodies))

    def fixture_claims(self, count: int, alternating_polarity: bool = False) -> None:
        claim_dir = self.repo / "canon" / "candidate_claims" / SUBJECT
        admiss_dir = self.repo / "receipts" / "immutable" / SUBJECT
        claim_template = yaml.safe_load((claim_dir / "claim-0001.yaml").read_text())
        admiss_template = yaml.safe_load((admiss_dir / "admissibility-0001.yaml").read_text())
        for path in claim_dir.glob("claim-*.yaml"):
            path.unlink()
        for path in admiss_dir.glob("admissibility-*.yaml"):
            path.unlink()
        for index in range(1, count + 1):
            claim = yaml.safe_load(yaml.safe_dump(claim_template))
            decision = yaml.safe_load(yaml.safe_dump(admiss_template))
            claim_id = f"pc.candidate_claim.{SUBJECT}.{index:04d}"
            claim["spec"]["claim_id"] = claim_id
            if alternating_polarity:
                claim["spec"]["normalized_claim_body"] = (
                    "alpha beta gamma delta no" if index % 2 else "alpha beta gamma delta")
            decision["spec"]["target_claim_ref"] = claim_id
            claim_dir.joinpath(f"claim-{index:04d}.yaml").write_text(yaml.safe_dump(claim))
            admiss_dir.joinpath(f"admissibility-{index:04d}.yaml").write_text(yaml.safe_dump(decision))

    def test_pair_quota_rejects_before_topology_writes(self):
        self.fixture_claims(92)
        corpus = self.repo / "canon" / "corpora" / SUBJECT / "index.yaml"
        original_corpus = corpus.read_bytes()
        result = self.run_script("scout_contradictions_and_supersession.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("4096 pair comparisons (4186)", result.stderr)
        self.assertEqual(corpus.read_bytes(), original_corpus)

    def test_output_quota_rejects_before_topology_writes(self):
        self.fixture_claims(34, alternating_polarity=True)
        corpus = self.repo / "canon" / "corpora" / SUBJECT / "index.yaml"
        original_corpus = corpus.read_bytes()
        output_dir = self.repo / "canon" / "contradictions" / SUBJECT
        before = {p.name: p.read_bytes() for p in output_dir.glob("*.yaml")}
        result = self.run_script("scout_contradictions_and_supersession.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("256 output artifacts", result.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in output_dir.glob("*.yaml")}, before)
        self.assertEqual(corpus.read_bytes(), original_corpus)

    def test_normal_topology_still_builds(self):
        result = self.run_script("scout_contradictions_and_supersession.py")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
