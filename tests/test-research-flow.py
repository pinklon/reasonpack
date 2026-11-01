#!/usr/bin/env python3
"""End-to-end offline orchestration regression tests."""
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "ops/research-flow.py"
PACK = ROOT / "examples/sample-reasonpack"


def invoke(*args):
    return subprocess.run([sys.executable, str(FLOW), *(str(x) for x in args)],
                          capture_output=True, text=True, timeout=120)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.job = Path(self.tmp.name) / "research"

    def test_prepare_all_depths_without_model_or_publication(self):
        for depth in ("short", "standard", "deep", "exhaustive"):
            job = Path(self.tmp.name) / depth
            result = invoke("prepare", "--pack", PACK, "--out", job, "--depth", depth)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "awaiting-public-evidence-registry")
            self.assertFalse(report["model_invoked"])
            self.assertFalse(report["publication_authorized"])
            self.assertTrue((job / "editorial-packet.json").is_file())
            admission = json.loads((job / "admission/depth-admission.json").read_text())
            self.assertEqual(admission["depth_profile"], depth)

    def test_reuse_rejected_and_missing_registry_holds(self):
        first = invoke("prepare", "--pack", PACK, "--out", self.job)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = invoke("prepare", "--pack", PACK, "--out", self.job)
        self.assertEqual(second.returncode, 2)
        self.assertIn("destination already exists", second.stderr)
        resume = invoke("compose", "--job", self.job, "--registry",
                        Path(self.tmp.name) / "missing.json")
        self.assertEqual(resume.returncode, 2)
        self.assertFalse((self.job / "composition").exists())

    def test_resume_with_bound_evidence_and_short_url(self):
        result = invoke("prepare", "--pack", PACK, "--out", self.job, "--depth", "deep")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet_path = self.job / "editorial-packet.json"
        packet = json.loads(packet_path.read_text())
        packet["source_url"] = "https://youtu.be/jNQXAC9IVRw"
        packet_path.write_text(json.dumps(packet))
        excerpt = "Fixture-only public-source excerpt; no verified external claim."
        registry = Path(self.tmp.name) / "evidence.json"
        registry.write_text(json.dumps({
            "schema": "ghostmesh.reasonpack.evidence.v1",
            "source_manifest_sha256": packet["source_manifest_sha256"],
            "transcript_sha256": packet["transcript_sha256"],
            "sources": [{
                "id": "src-synth0001",
                "url": "https://www.anthropic.com/research/emotion-concepts-function",
                "title": "Synthetic fixture", "publisher": "Fixture only",
                "evidence_type": "primary",
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "excerpt": excerpt, "excerpt_sha256": sha256(excerpt.encode()).hexdigest(),
            }],
        }))
        resume = invoke("compose", "--job", self.job, "--registry", registry)
        self.assertEqual(resume.returncode, 0, resume.stderr)
        self.assertEqual(json.loads(resume.stdout)["status"],
                         "ready-for-separately-authorized-reasoning")
        self.assertTrue((self.job / "composition/model-prompt.json").is_file())
        self.assertEqual(json.loads((self.job / "composition/model-prompt.json").read_text())
                         ["depth_profile"]["name"], "deep")

    def test_invalid_source_does_not_create_job(self):
        result = invoke("prepare", "--pack", self.tmp.name, "--out", self.job)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.job.exists())


if __name__ == "__main__":
    unittest.main()
