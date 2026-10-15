#!/usr/bin/env python3
"""Source-only root-ledger contracts; no root writes or Production changes."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"ops/acquisition-owner-prestart.py"
spec=importlib.util.spec_from_file_location("reasonpack_one_time_claim_tests",P)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

def grant(job="a"*64,nonce="b"*64,signature="c"*64):
    return {
      "job_id":job,"nonce":nonce,"grant_sha256":signature,
      "release_commit":"d"*40,"source_admission_sha256":"e"*64,
      "signed_gateway_sha256":"f"*64,"launch_authorized":True
    }

class OwnerPrestartTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp=Path(tmp.name)
        self.db=self.tmp/"claims.sqlite3"
        self.permits=self.tmp/"permits"
        self.permits.mkdir()
        with sqlite3.connect(self.db) as con:
            con.execute(M.TABLE_DDL)
    def test_first_claim_is_durable_and_replay_is_rejected(self):
        g=grant()
        receipt=M.claim_once(g,db=self.db,permitdir=self.permits)
        self.assertEqual(receipt["job_id"],g["job_id"])
        self.assertEqual(receipt["grant_sha256"],g["grant_sha256"])
        with sqlite3.connect(self.db) as con:
            result=con.execute("SELECT job_id,nonce,grant_sha256 FROM launch_claims").fetchall()
        self.assertEqual(result,[(g["job_id"],g["nonce"],g["grant_sha256"])])
        self.assertTrue(M.check_permit_bytes(g,
            (self.permits/(g["job_id"]+".json")).read_bytes()))
        with self.assertRaisesRegex(ValueError,"replay"):
            M.claim_once(g,db=self.db,permitdir=self.permits)
        # Even if a service-user somehow deletes the public permit, the
        # owner-private DB does not forget the original consumed claim.
        (self.permits/(g["job_id"]+".json")).unlink()
        with self.assertRaises(sqlite3.IntegrityError):
            M.claim_once(g,db=self.db,permitdir=self.permits)
    def test_same_nonce_cannot_authorize_different_job(self):
        M.claim_once(grant(),db=self.db,permitdir=self.permits)
        with self.assertRaises(sqlite3.IntegrityError):
            M.claim_once(grant(job="9"*64,signature="8"*64),
                         db=self.db,permitdir=self.permits)
    def test_same_grant_digest_cannot_move_to_another_job(self):
        M.claim_once(grant(),db=self.db,permitdir=self.permits)
        with self.assertRaises(sqlite3.IntegrityError):
            M.claim_once(grant(job="9"*64,nonce="8"*64),
                         db=self.db,permitdir=self.permits)
    def test_reject_forged_unsigned_or_malformed_claim(self):
        for bad in (
            dict(grant(),launch_authorized=False),
            dict(grant(),nonce="NOT_A_NONCE"),
            dict(grant(),release_commit="main"),
            dict(grant(),grant_sha256="z"*64)
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                M.claim_once(bad,db=self.db,permitdir=self.permits)
        with sqlite3.connect(self.db) as con:
            count=con.execute("SELECT COUNT(*) FROM launch_claims").fetchone()[0]
        self.assertEqual(count,0)
    def test_mutated_permit_cannot_authorize_different_grant(self):
        g=grant()
        M.claim_once(g,db=self.db,permitdir=self.permits)
        raw=(self.permits/(g["job_id"]+".json")).read_bytes()
        for field,value in (("grant_sha256","9"*64),("nonce","9"*64),
                            ("release_commit","9"*40),
                            ("signed_gateway_sha256","9"*64)):
            edited=dict(g)
            if field=="signed_gateway_sha256":edited[field]=value
            else:edited[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"does not match"):
                M.check_permit_bytes(edited,raw)
        with self.assertRaisesRegex(ValueError,"fields"):
            M.check_permit_bytes(g,json.dumps({"job_id":g["job_id"]}).encode())
    def test_owner_secret_ledger_is_not_in_service_job(self):
        self.assertEqual(str(M.DB),"/var/lib/ghostmesh/reasonpack/launch-claims.sqlite3")
        self.assertEqual(str(M.PERMITS),"/var/lib/ghostmesh/reasonpack/permits")
        self.assertNotIn("/workspaces/runs/",str(M.DB))
        self.assertEqual(str(M.JOBS),"/srv/ghostmesh/workspaces/runs/reasonpack-jobs")
        unit=(ROOT/"ops/systemd/ghostmesh-reasonpack-acquire@.service").read_text()
        self.assertIn("ExecStartPre=+/usr/bin/python3",unit)
        self.assertNotIn("ReadWritePaths=/var/lib",unit)
        self.assertNotIn("RuntimeMaxSec=7200",unit)
    def test_unprivileged_cli_cannot_claim_or_initialize(self):
        if os.geteuid()==0:
            self.skipTest("CI currently running as root")
        r=subprocess.run([sys.executable,str(P),"--job-id","a"*64],
                         capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,2)
        self.assertIn("root-only launch claim",r.stderr)
        r=subprocess.run([sys.executable,str(P),"--init-owner-ledger"],
                         capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,2)
        self.assertIn("root-only launch claim",r.stderr)
    def test_unauthorized_root_public_ledger_path_is_denied(self):
        with self.assertRaisesRegex(ValueError,"unapproved owner ledger path"):
            M.check_ledger_custody(db=self.db,permits=self.permits)
    def test_claim_is_atomic_for_concurrent_processes(self):
        # SQLite's BEGIN IMMEDIATE + unique indexes provide at-most-one
        # consumption, regardless of process interleavings.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures=[ex.submit(M.claim_once,grant(),db=self.db,permitdir=self.permits)
                     for _ in range(4)]
            results=[]
            for f in futures:
                try:results.append(("ok",f.result()))
                except (ValueError,sqlite3.IntegrityError,sqlite3.OperationalError) as e:
                    results.append(("hold",str(e)))
        self.assertEqual(sum(x=="ok" for x,_ in results),1)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM launch_claims").fetchone()[0],1)
    def test_runner_only_launches_after_owner_spent_permit(self):
        c=(ROOT/"ops/acquisition-cgroup-runner.py").read_text()
        self.assertIn("owner.verified_owner_permit(approved)",c)
        self.assertLess(c.index("owner.verified_owner_permit(approved)"),
                        c.index("backend.preflight()"))
        rootcmd=(ROOT/"ops/acquisition-owner-prestart.py").read_text()
        self.assertNotIn("subprocess.Popen(",rootcmd)
        self.assertNotIn("launch-real",rootcmd)
        self.assertNotIn("guard.lock(job)",rootcmd.split("def prestart(job_id):")[1].split("def main():")[0].replace(
            "# NEVER use guard.lock(job) as root: that lock would be root:root", ""))

if __name__=="__main__":unittest.main(verbosity=2)
