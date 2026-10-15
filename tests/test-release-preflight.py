#!/usr/bin/env python3
"""Read-only immutable release renderer tests, no systemd installation."""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("release_preflight_tests",ROOT/"ops/release-preflight.py")
P=importlib.util.module_from_spec(sp)
sp.loader.exec_module(P)
COMMIT="c"*40

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.out=Path(self.t.name)/"review-package"
    def test_local_cli_and_worker_pin_coherent(self):
        policy=P.review_sources()
        self.assertIn("KillMode=control-group",policy)
        self.assertIn("@IMMUTABLE_RELEASE_DIR@",policy)
    def test_immutable_commit_release_unit(self):
        unit=P.render(COMMIT)
        expected=str(P.release_path(COMMIT))
        self.assertEqual(unit.count(expected),2)
        self.assertIn("WorkingDirectory="+expected,unit)
        self.assertIn("ExecStart=/usr/bin/python3 "+expected+"/ops/acquisition-cgroup-runner.py --job-id %i",unit)
        self.assertNotIn("@IMMUTABLE_RELEASE_DIR@",unit)
        self.assertNotIn("/current/",unit)
        self.assertIn("KillMode=control-group",unit)
        self.assertIn("ReadWritePaths=/srv/ghostmesh/workspaces/runs/reasonpack-jobs/%i",unit)
    def test_reject_service_user_writable_or_symlinked_release_ancestor(self):
        from unittest import mock
        import types
        original=Path.lstat
        def bad_owner(obj,*args,**kwargs):
            result=original(obj,*args,**kwargs)
            if str(obj)=="/opt":
                return types.SimpleNamespace(st_mode=result.st_mode,
                    st_uid=1001)
            return result
        with mock.patch.object(Path,"lstat",bad_owner):
            with self.assertRaisesRegex(ValueError,"non-root-owned"):
                P.verify_root_owned_anchor()

    def test_release_root_is_root_controlled_opt_not_writable_workspace(self):
        self.assertEqual(str(P.RELEASE_ROOT),"/opt/ghostmesh/reasonpack/releases")
        self.assertNotIn("/workspaces/runtime/",P.render(COMMIT))


    def test_unsafe_host_fails_before_creating_release_review_proposal(self):
        import types
        original=Path.lstat
        def unsafe(obj,*a,**kw):
            value=original(obj,*a,**kw)
            if str(obj)=="/opt":
                return types.SimpleNamespace(st_mode=value.st_mode,st_uid=1001)
            return value
        with mock.patch.object(P,"git_revision",return_value=COMMIT):
            with mock.patch.object(Path,"lstat",unsafe):
                with self.assertRaisesRegex(ValueError,"non-root-owned"):
                    P.build(COMMIT,self.out)
        self.assertFalse(self.out.exists())

    def test_invalid_revision_rejected(self):
        for value in ("HEAD", "a"*39, "A"*40,"a"*40+"/..","../main",""):
            with self.subTest(value=value),self.assertRaises(ValueError):
                P.render(value)
    def test_proposal_is_private_and_never_installs(self):
        with mock.patch.object(P,"git_revision",return_value=COMMIT),mock.patch.object(
                P,"verify_root_owned_anchor",return_value=True):
            data=P.build(COMMIT,self.out)
        self.assertFalse(data["installer_executed"])
        record=json.loads((self.out/"preflight-receipt.json").read_text())
        service=(self.out/"ghostmesh-reasonpack-acquire@.service").read_bytes()
        self.assertEqual(record["rendered_unit_sha256"],sha256(service).hexdigest())
        self.assertEqual(record["source_cli_sha256"],sha256(P.CLI.read_bytes()).hexdigest())
        self.assertEqual(record["source_commit"],COMMIT)
        for field in ("installer_executed","systemd_unit_installed",
                      "unit_enabled","worker_started","network_requested",
                      "owner_authorization_bound_to_hash","public_release"):
            self.assertFalse(record[field],field)
        self.assertEqual(record["cgroup_kill_witness"],"NOT_ATTESTED")
        self.assertEqual((self.out/"preflight-receipt.json").stat().st_mode & 0o777,0o600)
        with mock.patch.object(P,"git_revision",return_value=COMMIT),mock.patch.object(
                P,"verify_root_owned_anchor",return_value=True):
            with self.assertRaisesRegex(ValueError,"already exists"):P.build(COMMIT,self.out)
    def test_unreviewed_commit_refused_without_output(self):
        with mock.patch.object(P,"git_revision",return_value="b"*40):
            with self.assertRaisesRegex(ValueError,"not exact owner-reviewed"):
                P.build(COMMIT,self.out)
        self.assertFalse(self.out.exists())
    def test_reject_worker_referring_to_mutable_global_binary(self):
        original=P.WORKER
        fake=Path(self.t.name)/"fake-worker.py"
        fake.write_text('REPO=Path(__file__).resolve().parents[1]\nCLI=Path("/home/ghostmesh/.local/share/reasonpack/reasonpack")\nPIN="fake"\n')
        with mock.patch.object(P,"module") as imported:
            imported.return_value=type("Fake",(),{
                "CLI":Path("/home/ghostmesh/.local/share/reasonpack/reasonpack"),
                "PIN":sha256(P.CLI.read_bytes()).hexdigest()})()
            with self.assertRaisesRegex(ValueError,"not pinned to same release"):
                P.review_sources()
    def test_unmanaged_launcher_does_not_exist(self):
        current=(ROOT/"ops/acquisition-supervisor.py").read_text()
        self.assertNotIn('sub.add_parser("launch-real")',current)
        self.assertNotIn('"launch-real"',current)
    def test_preflight_imports_do_not_mutate_checked_out_source(self):
        before={x.name for x in (ROOT/"ops"/"__pycache__").glob("*")} if (ROOT/"ops"/"__pycache__").exists() else set()
        env=os.environ.copy()
        env.pop("PYTHONDONTWRITEBYTECODE",None)
        script=("import runpy; m=runpy.run_path("+repr(str(ROOT/"ops/release-preflight.py"))+
                ",run_name='source_only_readback'); m['review_sources']()")
        result=subprocess.run([sys.executable,"-c",script],capture_output=True,
                              text=True,env=env,timeout=6)
        self.assertEqual(result.returncode,0,result.stderr)
        after={x.name for x in (ROOT/"ops"/"__pycache__").glob("*")} if (ROOT/"ops"/"__pycache__").exists() else set()
        self.assertEqual(before,after)

    def test_protected_unit_unmodified_in_source(self):
        unit=P.SOURCE_TEMPLATE.read_text()
        self.assertEqual(unit.count("@IMMUTABLE_RELEASE_DIR@"),2)
        self.assertNotIn("/runtime/reasonpack/current",unit)

if __name__=="__main__":
    unittest.main(verbosity=2)
