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
    def test_zombie_pid_never_counts_as_running(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location("supervisor_zombie_test",
              ROOT/"ops/acquisition-supervisor.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for status in ("Z","X","x"):
            fake="123 (fixture name) "+status+" "+" ".join(["0"]*18+["381299"])
            self.assertIsNone(module.parse_proc_identity(fake))
        running="123 (fixture name) S "+" ".join(["0"]*18+["381299"])
        self.assertEqual(module.parse_proc_identity(running),381299)

    def test_interrupted_registration_can_be_retried_without_partial_job(self):
        from unittest import mock
        import importlib.util
        spec=importlib.util.spec_from_file_location("supervisor_atomic_test",
              ROOT/"ops/acquisition-supervisor.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.dict(os.environ,{"REASONPACK_MAIL_INGEST_KEY":KEY.decode()}):
            with mock.patch.object(module.os,"rename",side_effect=OSError("synthetic interrupted registration")):
                with self.assertRaisesRegex(OSError,"interrupted registration"):
                    module.register(self.input,self.jobs,self.envelope,[SENDER])
        self.assertFalse(self.job.exists())
        self.assertEqual(list(self.jobs.glob(".register-acquisition-*")),[])
        self.assertEqual(self.register().returncode,0)
        self.assertEqual(self.observe()["status"],"registered-no-worker")

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
    def test_real_network_launch_requires_explicit_pin_and_operator_switch(self):
        self.assertEqual(self.register().returncode,0)
        wrong=cli("launch-real","--job",self.job,
                   "--permit-network-acquisition",
                   "--expected-cli-sha256","b"*64)
        self.assertEqual(wrong.returncode,2)
        self.assertEqual(self.observe()["status"],"registered-no-worker")
        unpermitted=cli("launch-real","--job",self.job,
                        "--expected-cli-sha256",
                        "2b9773f76223f4f7fe37b222c8b16639f41c4a692c350794338263ef25a214b1")
        self.assertEqual(unpermitted.returncode,2)
        self.assertEqual(self.observe()["status"],"registered-no-worker")
        self.assertFalse((self.job/"real-worker.stdout").exists())

    def test_real_backend_orphan_is_detected_without_automatic_kill_or_retry(self):
        self.assertEqual(self.register().returncode,0)
        fixture=subprocess.Popen(["/usr/bin/sleep","3"],start_new_session=True,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            import importlib.util
            spec=importlib.util.spec_from_file_location("real_orphan_supervisor",
                           ROOT/"ops/acquisition-supervisor.py")
            sup=importlib.util.module_from_spec(spec);spec.loader.exec_module(sup)
            s=json.loads((self.job/"supervision.json").read_text())
            s.update(status="running",worker_kind="real-acquisition",
                     worker_pid=999999,worker_start_ticks=123456,attempts=1)
            (self.job/"supervision.json").write_text(json.dumps(s))
            (self.job/"real-acquisition-heartbeat.json").write_text(json.dumps({
                "schema":"ghostmesh.reasonpack.acquisition-real-heartbeat.v1",
                "job_id":self.receipt["job_id"],"worker_pid":999999,
                "worker_start_ticks":123456,"backend_pid":fixture.pid,
                "backend_start_ticks":sup.startticks(fixture.pid),
                "backend_pgid":os.getpgid(fixture.pid),
                "sequence":1,"time_utc":"2026-10-15T17:00:00+00:00"}))
            observed=self.observe()
            self.assertEqual(observed["status"],
                             "orphaned-backend-active-reconciliation-required")
            self.assertEqual(observed["potential_orphan_backend"]["pid"],fixture.pid)
            self.assertFalse(observed["automatic_restart_authorized"])
            self.assertFalse(observed["artifact_verified"])
            self.assertIsNone(observed["verified_manifest_sha256"])
        finally:
            try:os.killpg(fixture.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            fixture.wait(timeout=3)

    def test_forged_real_source_receipt_is_not_acquisition_success(self):
        self.assertEqual(self.register().returncode,0)
        s=json.loads((self.job/"supervision.json").read_text())
        s.update(status="running",worker_kind="real-acquisition",worker_pid=999999,
                 worker_start_ticks=111111,attempts=1)
        (self.job/"supervision.json").write_text(json.dumps(s))
        (self.job/"real-acquisition-result.json").write_text(json.dumps({
            "schema":"ghostmesh.reasonpack.acquisition-real-backend.v1",
            "status":"WORKER_VERIFIED_SOURCE_PACKAGE",
            "job_id":"0"*64,"worker_pid":999999,"worker_start_ticks":111111,
            "manifest_sha256":"f"*64}))
        status=self.observe()
        self.assertEqual(status["status"],"reconciliation-required-no-auto-retry")
        self.assertFalse(status["artifact_verified"])
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
    def test_launch_log_collision_is_reconciliation_required_not_fresh(self):
        self.assertEqual(self.register().returncode,0)
        (self.job/"fixture.stdout").write_bytes(b"preexisting partial log")
        failed=self.launch(ticks=4,period=40)
        self.assertEqual(failed.returncode,2)
        self.assertEqual(self.observe()["status"],"reconciliation-required-launch-uncertain")
        self.assertFalse(self.observe()["automatic_restart_authorized"])
        self.assertEqual(self.launch().returncode,2)

    def test_subprocess_spawn_failure_retains_durable_attempt(self):
        from unittest import mock
        import importlib.util
        spec=importlib.util.spec_from_file_location("supervisor_spawn_test",
              ROOT/"ops/acquisition-supervisor.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(self.register().returncode,0)
        with mock.patch.object(module.subprocess,"Popen",side_effect=OSError("synthetic spawn failure")):
            with self.assertRaisesRegex(OSError,"spawn failure"):
                module.start_fixture(self.job,2,10)
        self.assertEqual(self.observe()["status"],"reconciliation-required-launch-uncertain")
        self.assertFalse(self.observe()["synthetic_completion_reported"])
        self.assertEqual(self.launch().returncode,2)

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
