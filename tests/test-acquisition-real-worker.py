#!/usr/bin/env python3
"""No-network tests of fixed ReasonPack production-adapter contract."""
from __future__ import annotations
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("acquisition_real_test",ROOT/"ops/acquisition-real-worker.py")
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
VID="jNQXAC9IVRw"
URL="https://www.youtube.com/watch?v="+VID
def h(raw):return sha256(raw).hexdigest()

def build_synthetic_package(out,vid=VID):
    # Exact-format fixture ONLY, not source provenance or an actual download.
    src=ROOT/"examples/sample-reasonpack"
    for file in src.iterdir():
        if file.is_file():shutil.copyfile(file,out/file.name)
    source=json.loads((out/"source.json").read_text())
    source["id"]=vid
    source["webpage_url"]="https://www.youtube.com/watch?v="+vid
    (out/"source.json").write_text(json.dumps(source,indent=2)+"\n")
    manifest=json.loads((out/"manifest.json").read_text())
    manifest["sourceUrl"]="https://www.youtube.com/watch?v="+vid
    manifest.pop("fixture",None)
    for row in manifest["members"]:
        member=out/row["path"]
        row["bytes"]=member.stat().st_size
        row["sha256"]=h(member.read_bytes())
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    inventory=[row["path"] for row in manifest["members"]]+["manifest.json"]
    (out/"SHA256SUMS.txt").write_text("".join(
      h((out/name).read_bytes())+"  "+name+"\n" for name in inventory))
    return out

class FakeProcess:
    seen=[]
    video_id=VID
    def __init__(self,argv,**kw):
        self.pid=os.getpid()
        self.seen.append((argv,kw))
        out=Path(argv[3])
        build_synthetic_package(out,self.video_id)
    def poll(self):return 0

def fake_verify(argv,**kw):
    return subprocess.run([str(ROOT/"bin/reasonpack"),"verify",argv[2]],**kw)

class RealAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.job=Path(self.temp.name)
        self.receipt={"job_id":"a"*64,"source_url":URL,"video_id":VID}
        self.binary=self.job/"fixed-source-test-only"
        self.binary.write_text("SYNTHETIC FIXTURE CODE, NOT A REAL DOWNLOADER\n")
        self.digest=h(self.binary.read_bytes())
        FakeProcess.seen=[]
        FakeProcess.video_id=VID
    def acquire(self):
        return A.execute(self.job,self.receipt,cli=self.binary,pin=self.digest,
              runner=FakeProcess,verify_runner=fake_verify,interval=0.005)
    def test_fixed_backend_plan_no_execution(self):
        r=A.preflight(self.binary,self.digest)
        self.assertFalse(r["network_acquisition_performed"])
        self.assertEqual(r["sha256"],self.digest)
        self.assertFalse((self.job/"raw-acquisition").exists())
    def test_fake_acquisition_verified_and_no_private_env(self):
        result=self.acquire()
        self.assertEqual(result["status"],"WORKER_VERIFIED_SOURCE_PACKAGE")
        self.assertEqual(result["source_id"],VID)
        self.assertFalse(result["public_release"])
        self.assertFalse(result["email_dispatched"])
        self.assertFalse(result["independent_public_origin_attested"])
        argv,kw=FakeProcess.seen[0]
        self.assertEqual(argv,[str(self.binary),"build",URL,str(self.job/"raw-acquisition")])
        self.assertTrue(kw["start_new_session"])
        self.assertNotIn("REASONPACK_MAIL_INGEST_KEY",kw["env"])
        self.assertNotIn("HOME",os.environ.get("REASONPACK_MAIL_INGEST_KEY",""))
        self.assertEqual((self.job/"real-acquisition-heartbeat.json").stat().st_mode & 0o777,0o600)
        self.assertEqual((self.job/"real-acquisition-result.json").stat().st_mode & 0o777,0o600)
        self.assertEqual(A.verify_source(self.job,self.receipt,
                         verifier=self.binary,run=fake_verify)["source_id"],VID)
        with self.assertRaisesRegex(ValueError,"already exists"):self.acquire()
    def test_binary_drift_fails_before_side_effects(self):
        with self.assertRaisesRegex(ValueError,"drift"):
            A.execute(self.job,self.receipt,cli=self.binary,pin="f"*64,
               runner=FakeProcess,verify_runner=fake_verify)
        self.assertFalse((self.job/"raw-acquisition").exists())
    def test_backend_nonzero_does_not_publish_completion(self):
        class Failed:
            def __init__(self,argv,**kw):self.pid=os.getpid()
            def poll(self):return 2
        with self.assertRaisesRegex(ValueError,"exited without verified source"):
            A.execute(self.job,self.receipt,cli=self.binary,pin=self.digest,
                      runner=Failed,verify_runner=fake_verify)
        self.assertFalse((self.job/"real-acquisition-result.json").exists())
        self.assertTrue((self.job/"raw-acquisition").exists())
        self.assertFalse(A.output_hint(self.job/"raw-acquisition").startswith("unverified-manifest"))

    def test_wrong_source_id_not_accepted(self):
        FakeProcess.video_id="ZhM29Ds-mBg"
        with self.assertRaisesRegex(ValueError,"source manifest/video identity"):
            self.acquire()
        self.assertFalse((self.job/"real-acquisition-result.json").exists())
    def test_corrupted_source_pack_rejected_on_readback(self):
        self.acquire()
        pack=self.job/"raw-acquisition"
        (pack/"transcript.txt").write_bytes(b"tamper")
        with self.assertRaisesRegex(ValueError,"verifier rejected"):
            A.verify_source(self.job,self.receipt,
                            verifier=self.binary,run=fake_verify)
    def test_missing_media_rejected_even_with_rewritten_manifest(self):
        self.acquire()
        (self.job/"raw-acquisition"/"video.mp4").unlink()
        with self.assertRaises(ValueError):
            A.verify_source(self.job,self.receipt,
                            verifier=self.binary,run=fake_verify)
    def test_explicit_launch_flag_required(self):
        # The source supervisor never infers real download authorization.
        p=subprocess.run([sys.executable,str(ROOT/"ops/acquisition-supervisor.py"),
          "launch-real","--job",str(self.job),"--expected-cli-sha256",A.PIN],
          capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
        self.assertFalse((self.job/"raw-acquisition").exists())

if __name__=="__main__":unittest.main(verbosity=2)
