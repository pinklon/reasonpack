#!/usr/bin/env python3
"""End-to-end offline ReasonPack editorial pipeline contract, synthetic data only."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from email import message_from_binary_file

ROOT=Path(__file__).resolve().parents[1]
TEST_VIDEO="jNQXAC9IVRw"

def hashed(raw):
    return hashlib.sha256(raw).hexdigest()

def testpack(dest, vid=TEST_VIDEO):
    """Generate a synthetic packet solely for offline state-machine integration tests.

    This tests the integrity protocol, not authentic YouTube acquisition.
    """
    shutil.copytree(ROOT/"examples/sample-reasonpack",dest)
    src=dest/"source.json"
    s=json.loads(src.read_text())
    s["id"]=vid
    s["title"]="SYNTHETIC END-TO-END TEST: never publish"
    s["webpage_url"]="https://www.youtube.com/watch?v="+vid
    src.write_text(json.dumps(s,indent=2)+"\n")
    manifest_file=dest/"manifest.json"
    manifest=json.loads(manifest_file.read_text())
    manifest.pop("fixture",None)
    manifest["sourceUrl"]="https://www.youtube.com/watch?v="+vid
    for member in manifest["members"]:
        path=dest/member["path"]
        member["sha256"]=hashed(path.read_bytes())
        member["bytes"]=path.stat().st_size
    manifest_file.write_text(json.dumps(manifest,indent=2)+"\n")
    # This is an invented test bundle, not evidence of the public video.
    (dest/"SHA256SUMS.txt").write_text(
        "".join(hashed((dest/f).read_bytes())+"  "+f+"\n" for f in
            [*[m["path"] for m in manifest["members"]],"manifest.json"]))
    return dest

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.key=b"not-for-production-test-reasonpack-key-"*2
        self.vid=TEST_VIDEO
        self.email=self.root/"verified-envelope.json"
        self.jobs=self.root/"admitted"
        self.pipeline=self.root/"workflow"
        self.analysis=self.root/"analysis.json"
        d=json.loads((ROOT/"examples/reader-synthetic-analysis.json").read_text())
        d["video_id"]=self.vid
        self.analysis.write_text(json.dumps(d))
        self.pack=testpack(self.root/"synthetic-source")
        self.sign_envelope()

    def sign_envelope(self):
        self.sender="owner-test@example.org"
        e={"schema":"ghostmesh.reasonpack.mail-intake.v1",
           "verified_sender":self.sender,"message_id":"<test-1@example.org>",
           "gateway_authenticated":True,"policy_admitted":True,
           "issued_at_utc":datetime.now(timezone.utc).isoformat(),
           "subject":"ReasonPack test","body_text":"ReasonPack https://youtu.be/"+self.vid,
           "gateway":"offline-synthetic-test"}
        raw=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
        e["auth_tag"]=hmac.new(self.key,raw,"sha256").hexdigest()
        self.email.write_text(json.dumps(e))
    def cli(self,program,*args,extra_env=None):
        env=os.environ.copy()
        env["REASONPACK_MAIL_INGEST_KEY"]=self.key.decode()
        env["PYTHONDONTWRITEBYTECODE"]="1"
        if extra_env:env.update(extra_env)
        return subprocess.run([sys.executable,str(ROOT/"ops"/program),*map(str,args)],env=env,capture_output=True,text=True)
    def admission(self):
        r=self.cli("mail-reasonpack.py","admit","--envelope",self.email,
                   "--allow-sender",self.sender,"--out",self.jobs)
        self.assertEqual(r.returncode,0,r.stderr)
        return next(self.jobs.rglob("*.json"))
    def init(self):
        item=self.admission()
        r=self.cli("reader-pipeline.py","init","--admission",item,"--root",self.pipeline)
        self.assertEqual(r.returncode,0,r.stderr)
        return self.pipeline/json.loads(r.stdout)["job"]
    def progress(self,job,step,*args):
        r=self.cli("reader-pipeline.py",step,"--job",job,*args)
        self.assertEqual(r.returncode,0,step+": "+r.stderr)
        return json.loads(r.stdout)
    def test_end_to_end_produces_private_threaded_eml(self):
        job=self.init()
        self.assertEqual(self.progress(job,"source","--pack",self.pack)["state"],"source-verified")
        self.assertEqual(self.progress(job,"research")["state"],"awaiting-research")
        self.assertEqual(self.progress(job,"analysis","--analysis",self.analysis)["state"],"analysis-unreviewed")
        self.assertEqual(self.progress(job,"render")["state"],"reader-private-draft")
        self.assertEqual(self.progress(job,"draft","--from-email","ghostmesh@example.org")["state"],"email-private-draft")
        with (job/"draft.eml").open("rb") as f: msg=message_from_binary_file(f)
        self.assertEqual(msg.get("In-Reply-To"),"<test-1@example.org>")
        self.assertEqual(msg.get("X-GhostMesh-Draft-Only"),"true")
        self.assertEqual(msg.get("To"),self.sender)
        self.assertTrue(any(x.get_filename()=="GhostMesh-ReasonPack-Reader.html" for x in msg.walk()))
        flow=json.loads((job/"workflow.json").read_text())
        self.assertEqual([v["to"] for v in flow["events"]],
                        ["source-verified","awaiting-research","analysis-unreviewed","reader-private-draft","email-private-draft"])
        self.assertFalse(flow["publication_authority"])
        self.assertFalse(flow["dispatch_authority"])
        self.assertTrue(all(x["evidence"] for x in flow["events"]))
        self.assertEqual((job/"draft.eml").stat().st_mode & 0o777,0o600)
        self.assertEqual(self.cli("reader-pipeline.py","draft","--job",job,"--from-email","ghostmesh@example.org").returncode,2)

    def test_source_cannot_be_skipped(self):
        job=self.init()
        self.assertEqual(self.cli("reader-pipeline.py","research","--job",job).returncode,2)
        self.assertEqual(json.loads((job/"workflow.json").read_text())["state"],"admitted")

    def test_reject_wrong_video(self):
        job=self.init()
        bad=self.root/"other-pack"
        testpack(bad, "ZhM29Ds-mBg")
        self.assertEqual(self.cli("reader-pipeline.py","source","--job",job,"--pack",bad).returncode,2)
        self.assertEqual(json.loads((job/"workflow.json").read_text())["state"],"admitted")

    def test_tampered_research_packet_holds(self):
        job=self.init()
        self.progress(job,"source","--pack",self.pack)
        self.progress(job,"research")
        p=job/"research-input.json"
        p.write_text(p.read_text()+"\n")
        self.assertEqual(self.cli("reader-pipeline.py","analysis","--job",job,"--analysis",self.analysis).returncode,2)
        self.assertEqual(json.loads((job/"workflow.json").read_text())["state"],"awaiting-research")

    def test_duplicate_idempotency_and_mutated_request_rejected(self):
        job=self.init()
        rec=next(self.jobs.rglob("*.json"))
        self.assertEqual(json.loads(self.cli("reader-pipeline.py","init","--admission",rec,"--root",self.pipeline).stdout)["status"],"duplicate")
        change=json.loads(rec.read_text());change["subject"]="tampered"
        rec.write_text(json.dumps(change))
        self.assertEqual(self.cli("reader-pipeline.py","init","--admission",rec,"--root",self.pipeline).returncode,2)

    def test_tamper_verified_source_fails_next_stage(self):
        job=self.init()
        self.progress(job,"source","--pack",self.pack)
        (self.pack/"transcript.txt").write_text("tampered")
        self.assertEqual(self.cli("reader-pipeline.py","research","--job",job).returncode,2)
        self.assertEqual(json.loads((job/"workflow.json").read_text())["state"],"source-verified")

if __name__=="__main__":
    unittest.main(verbosity=2)
