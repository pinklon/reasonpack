#!/usr/bin/env python3
"""Offline durable acquisition supervisor crash/restart/no-timeout tests."""
from __future__ import annotations
from hashlib import sha256
import json
import hmac
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import signal
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
KEY=b"synthetic-owner-gateway-signature-test"*2
SENDER="owner-test@example.org"
def cli(*args):
    return subprocess.run([sys.executable,str(ROOT/"ops/acquisition-supervisor.py"),
                           *map(str,args)],capture_output=True,text=True,timeout=7,
                          env={**os.environ,"REASONPACK_MAIL_INGEST_KEY":KEY.decode()})
def admission(dest,envelope,source_id="jNQXAC9IVRw"):
    original={
        "schema":"ghostmesh.reasonpack.mail-intake.v1",
        "verified_sender":SENDER,
        "message_id":"<synthetic-reasonpack-123@example.org>",
        "gateway_authenticated":True,"policy_admitted":True,
        "issued_at_utc":datetime.now(timezone.utc).isoformat(),
        "subject":"ReasonPack request",
        "body_text":"Please generate a ReasonPack for https://youtu.be/"+source_id,
        "gateway":"offline-synthetic-test"}
    raw=json.dumps(original,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    original["auth_tag"]=hmac.new(KEY,raw,"sha256").hexdigest()
    envelope.write_text(json.dumps(original))
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        run=cli("admit","--envelope",envelope) if False else subprocess.run(
            [sys.executable,str(ROOT/"ops/mail-reasonpack.py"),"admit",
             "--envelope",str(envelope),"--allow-sender",SENDER,
             "--out",tmp],capture_output=True,text=True,
             env={**os.environ,"REASONPACK_MAIL_INGEST_KEY":KEY.decode()})
        if run.returncode:raise AssertionError(run.stderr)
        item=json.loads(next(Path(tmp).rglob("*.json")).read_text())
        dest.write_text(json.dumps(item))
        return item
class DurableTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.input=self.root/"admitted.json"
        self.envelope=self.root/"signed-envelope.json"
        self.receipt=admission(self.input,self.envelope)
        self.jobs=self.root/"queue"
        self.job=self.jobs/self.receipt["job_id"]
        self.child=None
        self.addCleanup(self.ensure_child_stopped)
    def ensure_child_stopped(self):
        if self.child:
            try:os.kill(self.child,signal.SIGTERM)
            except ProcessLookupError:pass
    def register(self):
        return cli("register","--admission",self.input,"--root",self.jobs,
                   "--envelope",self.envelope,"--allow-sender",SENDER)
    def launch(self,ticks=10,period=65):
        r=cli("launch-fixture","--job",self.job,"--ticks",ticks,"--period-ms",period)
        if r.returncode==0:self.child=json.loads(r.stdout)["pid"]
        return r
    def observe(self):
        r=cli("status","--job",self.job)
        if r.returncode:raise AssertionError(r.stderr)
        return json.loads(r.stdout)
    def wait_for(self,statuses,secs=4):
        started=time.monotonic()
        last=None
        while time.monotonic()-started<secs:
            result=self.observe()
            last=result["status"]
            if last in statuses:return result
            time.sleep(.05)
        self.fail("status did not reach "+str(statuses)+" last="+str(last))
    def test_admission_idempotent_and_private(self):
        self.assertEqual(self.register().returncode,0)
        self.assertEqual(json.loads(self.register().stdout)["status"],"already-registered")
        self.assertEqual((self.job/"admission.json").stat().st_mode & 0o777,0o600)
        self.assertEqual(self.observe()["status"],"registered-no-worker")
        self.assertIsNone(self.observe()["mission_elapsed_cutoff"])
        self.assertFalse(self.observe()["production_acquisition_qualified"])
    def test_restart_safe_completion_without_time_limit(self):
        self.assertEqual(self.register().returncode,0)
        launch=self.launch(ticks=8,period=80)
        self.assertEqual(launch.returncode,0,launch.stderr)
        first=self.wait_for({"running-worker-reported-progress","completion-reported-process-still-running",
                             "synthetic-fixture-complete"})
        self.assertEqual(first["worker_pid"],self.child)
        self.assertFalse(first["independent_progress_witness"])
        finished=self.wait_for({"synthetic-fixture-complete"},secs=4)
        self.assertTrue(finished["synthetic_completion_reported"])
        self.assertFalse(finished["independent_completion_attested"])
        self.assertEqual(finished["last_progress_sequence"],8)
        self.assertIsNone(finished["mission_elapsed_cutoff"])
        self.assertFalse(finished["email_dispatched"])
        self.assertEqual(self.launch().returncode,2)
    def test_missing_worker_requires_reconciliation_not_retry(self):
        self.assertEqual(self.register().returncode,0)
        launch=self.launch(ticks=30,period=200)
        self.assertEqual(launch.returncode,0,launch.stderr)
        self.wait_for({"running-worker-reported-progress"})
        os.kill(self.child,signal.SIGKILL)
        stopped=self.wait_for({"reconciliation-required-no-auto-retry"},secs=3)
        self.assertFalse(stopped["automatic_restart_authorized"])
        self.assertFalse(stopped["synthetic_completion_reported"])
        self.assertEqual(self.launch().returncode,2)
    def test_unauthenticated_input_cannot_grant_mail(self):
        bad=json.loads(self.input.read_text())
        bad["email_dispatch_authority"]=True
        self.input.write_text(json.dumps(bad))
        self.assertEqual(self.register().returncode,2)
        self.assertFalse(self.job.exists())
    def test_rejected_forged_signature(self):
        altered=json.loads(self.envelope.read_text())
        altered["verified_sender"]="attacker@example.org"
        self.envelope.write_text(json.dumps(altered))
        self.assertEqual(self.register().returncode,2)
        self.assertFalse(self.job.exists())

    def test_signed_request_source_binding(self):
        wrong=json.loads(self.input.read_text())
        wrong["source_url"]="https://www.youtube.com/watch?v=ZhM29Ds-mBg"
        wrong["video_id"]="ZhM29Ds-mBg"
        self.input.write_text(json.dumps(wrong))
        self.assertEqual(self.register().returncode,2)
        self.assertFalse(self.job.exists())

    def test_invalid_video_source_rejected(self):
        bad=json.loads(self.input.read_text())
        bad["source_url"]="https://evil.example/watch?v=jNQXAC9IVRw"
        self.input.write_text(json.dumps(bad))
        self.assertEqual(self.register().returncode,2)
    def test_same_job_with_changed_admission_denied(self):
        self.assertEqual(self.register().returncode,0)
        changed=json.loads(self.input.read_text())
        changed["sender"]="different@example.org"
        self.input.write_text(json.dumps(changed))
        self.assertEqual(self.register().returncode,2)
    def test_no_live_worker_without_qualified_adapter(self):
        self.assertEqual(self.register().returncode,0)
        before=set(self.job.iterdir())
        self.assertEqual(self.observe()["status"],"registered-no-worker")
        self.assertEqual(before,set(self.job.iterdir()))
        self.assertFalse((self.job/"synthetic-completion.json").exists())
    def test_forged_heartbeat_cannot_change_process_identity(self):
        self.assertEqual(self.register().returncode,0)
        self.assertEqual(self.launch(ticks=12,period=90).returncode,0)
        current=self.wait_for({"running-worker-reported-progress"})
        heartbeat=self.job/"heartbeat.json"
        heartbeat.write_text(json.dumps({"schema":"ghostmesh.reasonpack.synthetic-heartbeat.v1",
          "job_id":self.receipt["job_id"],"worker_pid":999999,
          "worker_start_ticks":0,"sequence":9876,"observed_at_utc":"2099-01-01T00:00:00+00:00"}))
        observed=self.observe()
        self.assertNotEqual(observed.get("last_progress_sequence"),9876)
        self.assertFalse(observed["email_dispatched"])
        self.wait_for({"synthetic-fixture-complete"},secs=4)
    def test_forged_completion_without_process_cannot_report_success(self):
        self.assertEqual(self.register().returncode,0)
        (self.job/"synthetic-completion.json").write_text(json.dumps({
          "schema":"ghostmesh.reasonpack.synthetic-completion.v1",
          "job_id":self.receipt["job_id"],"worker_pid":123,
          "worker_start_ticks":42,"complete":True}))
        self.assertEqual(self.observe()["status"],"registered-no-worker")
        self.assertFalse(self.observe()["synthetic_completion_reported"])

if __name__=="__main__":unittest.main(verbosity=2)
