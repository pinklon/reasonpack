#!/usr/bin/env python3
"""No-network, synthetic signer and adversarial admission grant tests.

Temporary Ed25519 PRIVATE KEYS exist only within disposable local test dirs.
No signer/private key is committed, installed, or given to the real worker.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("reasonpack_owner_grant_under_test",ROOT/"ops/acquisition-signed-grant.py")
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
RELEASE="b"*40
JOB="a"*64
VID="ZhM29Ds-mBg"
SOURCE="https://www.youtube.com/watch?v="+VID
SIGNED_GATEWAY="c"*64

def generated_key(base):
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-C",
        "synthetic-test-only","-f",str(base)],capture_output=True,check=True,timeout=8)
    return base

class OwnerGrantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("ssh-keygen"):
            raise unittest.SkipTest("OpenSSH signature verifier unavailable")
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.private=generated_key(self.root/"testsigner")
        pub=(self.root/"testsigner.pub").read_text().split()
        self.allowed=self.root/"approved_signers"
        self.allowed.write_text(f"{M.PRINCIPAL} {pub[0]} {pub[1]}\n")
        self.admission={
            "schema":"ghostmesh.reasonpack.mail-job.v1",
            "status":"admitted-awaiting-acquisition",
            "job_id":JOB,
            "source_url":SOURCE,
            "video_id":VID,
            "email_dispatch_authority":False,
            "publication_authority":False}
        self.admission_raw=(json.dumps(self.admission,sort_keys=True)+"\n").encode()
        self.supervision={"job_id":JOB,"admission_sha256":sha256(self.admission_raw).hexdigest(),
             "signed_gateway_sha256":SIGNED_GATEWAY,"status":"registered","attempts":0}
        self.now=datetime(2026,10,15,20,0,tzinfo=timezone.utc)
        self.data={
          "schema":M.SCHEMA,"job_id":JOB,"source_url":SOURCE,"video_id":VID,
          "admission_sha256":sha256(self.admission_raw).hexdigest(),
          "signed_gateway_sha256":SIGNED_GATEWAY,
          "release_commit":RELEASE,
          "scope":"owner-only-real-acquisition","nonce":"d"*64,
          "issued_at_utc":(self.now-timedelta(minutes=5)).isoformat(),
          "expires_at_utc":(self.now+timedelta(hours=3)).isoformat()}
    def raw(self,data=None):
        return (json.dumps(data or self.data,sort_keys=True,
                          separators=(",",":"),ensure_ascii=True)+"\n").encode()
    def sign(self,raw,private=None):
        src=self.root/"payload"
        src.write_bytes(raw)
        result=subprocess.run(["ssh-keygen","-Y","sign","-f",str(private or self.private),
            "-n",M.NAMESPACE,str(src)],capture_output=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stderr)
        return (self.root/"payload.sig").read_bytes()
    def payload(self,raw=None,supervision=None,release=RELEASE,now=None):
        return M.validate_payload(raw or self.raw(),admission_raw=self.admission_raw,
            supervision=supervision or self.supervision,
            release_commit=release,now=now or self.now)
    def test_valid_signature_and_entire_intent_bound(self):
        raw=self.raw()
        sig=self.sign(raw)
        record=self.payload(raw)
        self.assertEqual(record["job_id"],JOB)
        self.assertFalse(record["launch_authorized"]) # only cryptographic verification upgrades this
        self.assertTrue(M.verify_file_signature(raw,sig,self.allowed))
    def test_admission_binds_exact_source_bytes_not_just_json_fields(self):
        different=(json.dumps(self.admission,indent=4)+"\n").encode()
        with self.assertRaisesRegex(ValueError,"registered authenticated Gmail intent"):
            M.validate_payload(self.raw(),admission_raw=different,
                supervision=self.supervision,release_commit=RELEASE,now=self.now)
    def test_reject_tampered_video_and_job(self):
        for field,bad in (("video_id","XXXXXXXXXXX"),
                          ("source_url","https://www.youtube.com/watch?v=XXXXXXXXXXX"),
                          ("job_id","e"*64),
                          ("signed_gateway_sha256","e"*64)):
            with self.subTest(field=field):
                obj=dict(self.data);obj[field]=bad
                with self.assertRaisesRegex(ValueError,"registered authenticated Gmail intent"):
                    self.payload(self.raw(obj))
    def test_reject_other_immutable_release(self):
        with self.assertRaisesRegex(ValueError,"immutable release"):
            self.payload(release="f"*40)
    def test_reject_wrong_signed_gateway_receipt(self):
        s=dict(self.supervision,signed_gateway_sha256="e"*64)
        with self.assertRaisesRegex(ValueError,"registered authenticated Gmail intent"):
            self.payload(supervision=s)
    def test_reject_forged_grant_and_altered_signature(self):
        raw=self.raw()
        signature=self.sign(raw)
        altered=bytearray(signature);altered[-12]^=1
        with self.assertRaisesRegex(ValueError,"signature invalid"):
            M.verify_file_signature(raw,bytes(altered),self.allowed)
        changed=dict(self.data,nonce="e"*64)
        with self.assertRaisesRegex(ValueError,"signature invalid"):
            M.verify_file_signature(self.raw(changed),signature,self.allowed)
    def test_reject_another_public_signer(self):
        outsider=generated_key(self.root/"outsider")
        signature=self.sign(self.raw(),outsider)
        with self.assertRaisesRegex(ValueError,"signature invalid"):
            M.verify_file_signature(self.raw(),signature,self.allowed)
    def test_expired_and_too_long_grants(self):
        with self.assertRaisesRegex(ValueError,"grant expired"):
            self.payload(now=self.now+timedelta(hours=5))
        obj=dict(self.data,expires_at_utc=(self.now+timedelta(days=2)).isoformat())
        with self.assertRaisesRegex(ValueError,"grant expired"):
            self.payload(self.raw(obj))
    def test_reject_scope_field_injection_or_noncanonical_serialization(self):
        obj=dict(self.data,scope="public")
        with self.assertRaisesRegex(ValueError,"grant scope"):
            self.payload(self.raw(obj))
        obj=dict(self.data,public_dispatch=True)
        with self.assertRaisesRegex(ValueError,"grant fields"):
            self.payload(self.raw(obj))
        with self.assertRaisesRegex(ValueError,"noncanonical signed"):
            self.payload((json.dumps(self.data,indent=2)+"\n").encode())
    def test_missing_production_registry_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"unapproved public signer registry"):
            M.check_root_public_signer_custody(self.root/"nonexistent")
        with self.assertRaisesRegex(ValueError,"owner-controlled public signer registry"):
            M.check_root_public_signer_custody()
    def test_full_job_grant_verifies_with_synthetic_public_signer(self):
        job=self.root/JOB
        job.mkdir()
        raw=self.raw()
        (job/"launch-grant.json").write_bytes(raw)
        (job/"launch-grant.sig").write_bytes(self.sign(raw))
        # Test substitutes a disposable PUBLIC key only, never a production
        # signer or a private key in the actual worker.
        with mock.patch.object(M,"TRUST",self.allowed),mock.patch.object(
                M,"check_root_public_signer_custody",return_value=True):
            result=M.verify_for_job(job,self.admission_raw,self.supervision,RELEASE)
        self.assertTrue(result["launch_authorized"])
        self.assertEqual(result["grant_sha256"],sha256(raw).hexdigest())
        self.assertEqual(result["signature_method"],
                         "openssh-ed25519-external-owner-signer")
        # Signature no longer matches if a worker mutates the grant.
        changed=dict(self.data,nonce="e"*64)
        (job/"launch-grant.json").write_bytes(self.raw(changed))
        with mock.patch.object(M,"TRUST",self.allowed),mock.patch.object(
                M,"check_root_public_signer_custody",return_value=True):
            with self.assertRaisesRegex(ValueError,"signature invalid"):
                M.verify_for_job(job,self.admission_raw,self.supervision,RELEASE)

    def test_production_method_refuses_untrusted_signers(self):
        job=self.root/JOB
        job.mkdir()
        (job/"launch-grant.json").write_bytes(self.raw())
        (job/"launch-grant.sig").write_bytes(self.sign(self.raw()))
        with self.assertRaisesRegex(ValueError,"owner-controlled public signer registry"):
            M.verify_for_job(job,self.admission_raw,self.supervision,RELEASE)
    def test_crypto_validated_grant_cannot_rebind_other_job(self):
        raw=self.raw()
        sig=self.sign(raw)
        self.assertTrue(M.verify_file_signature(raw,sig,self.allowed))
        self.admission["job_id"]="f"*64
        self.admission_raw=(json.dumps(self.admission,sort_keys=True)+"\n").encode()
        with self.assertRaisesRegex(ValueError,"registered authenticated Gmail intent"):
            self.payload(raw)
    def test_no_private_signer_tool_or_key_in_repo(self):
        source=(ROOT/"ops/acquisition-signed-grant.py").read_text()
        self.assertNotIn("ssh-keygen -Y sign",source)
        runner=(ROOT/"ops/acquisition-cgroup-runner.py").read_text()
        self.assertIn('custody.verify_for_job',runner)
        self.assertLess(runner.index("custody.verify_for_job"),runner.index("backend.preflight()"))
        self.assertLess(runner.index("custody.verify_for_job"),runner.index('state.update(status="launch-intent-uncertain"'))

if __name__=="__main__": unittest.main(verbosity=2)
