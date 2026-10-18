#!/usr/bin/env python3
"""Offline source-only service cgroup containment policy tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess
import os
import sys
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
UNIT=ROOT/"ops/systemd/ghostmesh-reasonpack-acquire@.service"
spec=importlib.util.spec_from_file_location("cgroup_contract",ROOT/"ops/acquisition-cgroup-runner.py")
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
IDENT="a"*64

class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.unit=UNIT.read_text()
    def test_systemd_policy_source_is_valid_without_installing(self):
        result=C.verify_install_contract(self.unit)
        self.assertEqual(result["status"],"source-policy-validated-not-installed")
        self.assertEqual(result["cgroup_kill_policy"],"control-group")
        self.assertIsNone(result["total_duration_limit"])
        self.assertFalse(result["network_acquisition_performed"])
    def test_exact_instance_cgroup_required(self):
        expected="ghostmesh-reasonpack-acquire@"+IDENT+".service"
        self.assertEqual(C.verify_containment(IDENT,
            "/system.slice/"+expected),expected)
        for cgroup in (
            "/system.slice/ghostmesh-commons-responder.service",
            "/user.slice/user-1001.slice",
            "/system.slice/"+expected+"/child",
            "/system.slice/ghostmesh-reasonpack-acquire@"+"b"*64+".service",
            "/system.slice/other"+expected,
            "/user.slice/user-1001.slice/user@1001.service/app.slice/"+expected,
            "/malicious.slice/"+expected,
            "",
        ):
            with self.subTest(cgroup=cgroup),self.assertRaises(ValueError):
                C.verify_containment(IDENT,cgroup)
    def test_only_systemd_main_pid_can_run_foreground_owner_claim(self):
        class Result:
            returncode=0
            stdout=str(987654321)
        with mock.patch.object(C,"verify_containment",return_value="test-unit"):
            with self.assertRaisesRegex(ValueError,"primary runner"):
                C.verify_primary_runner(IDENT,run=lambda *a,**k:Result())
        class Own:
            returncode=0
            stdout=str(os.getpid())
        with mock.patch.object(C,"verify_containment",return_value="test-unit"):
            item=C.verify_primary_runner(IDENT,run=lambda *a,**k:Own())
            self.assertEqual(item["main_pid"],os.getpid())
        class Missing:
            returncode=1
            stdout=""
        with mock.patch.object(C,"verify_containment",return_value="test-unit"):
            with self.assertRaisesRegex(ValueError,"not authoritative"):
                C.verify_primary_runner(IDENT,run=lambda *a,**k:Missing())

    def test_invalid_or_unescaped_unit_identifier_rejected(self):
        for name in ("../"+IDENT,"a"*63,"A"*64,"a"*64+"/escape","abc"):
            with self.assertRaises(ValueError):
                C.verify_containment(name,"/system.slice/ghostmesh-reasonpack-acquire@"+name+".service")
    def test_direct_real_worker_executable_cannot_bypass_cgroup(self):
        result=subprocess.run([sys.executable,str(ROOT/"ops/acquisition-real-worker.py"),
             "--job",str(C.JOBS/IDENT),"--gate-fd","0","--admission-fd","0"],
             input="",capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,2)
        self.assertIn("exact approved systemd instance cgroup",result.stderr)

    def test_noncontained_main_cannot_perform_network_acquisition(self):
        result=subprocess.run([sys.executable,str(ROOT/"ops/acquisition-cgroup-runner.py"),
            "--job-id",IDENT,"--check-only"],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,2)
        self.assertIn("exact approved systemd instance cgroup",result.stderr)
    def test_reject_broad_service_kill_policy(self):
        with self.assertRaisesRegex(ValueError,"KillMode"):
            C.verify_install_contract(self.unit.replace("KillMode=control-group","KillMode=process"))
    def test_reject_arbitrary_global_duration_cutoff(self):
        with self.assertRaisesRegex(ValueError,"RuntimeMaxSec"):
            C.verify_install_contract(self.unit.replace("RuntimeMaxSec=infinity","RuntimeMaxSec=7200"))
    def test_reject_broad_writable_filesystem(self):
        with self.assertRaisesRegex(ValueError,"write authority"):
            C.verify_install_contract(self.unit.replace(
               "ReadWritePaths=/srv/ghostmesh/workspaces/runs/reasonpack-jobs/%i",
               "ReadWritePaths=/srv/ghostmesh"))
    def test_reject_service_as_root(self):
        with self.assertRaisesRegex(ValueError,"User"):
            C.verify_install_contract(self.unit.replace("User=ghostmesh","User=root"))
    def test_reject_external_command_replacement(self):
        with self.assertRaisesRegex(ValueError,"immutable release rendering"):
            C.verify_install_contract(self.unit.replace("acquisition-cgroup-runner.py","/bin/sh"))
    def test_reject_missing_memory_or_process_ceiling(self):
        for value in ("MemoryMax=8G","TasksMax=128","CPUQuota=200%"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                C.verify_install_contract(self.unit.replace(value,""))
    def test_missing_real_job_cannot_launch_even_with_mocked_cgroup(self):
        with mock.patch.object(C,"verify_primary_runner",return_value={"unit":"test","main_pid":1}):
            with self.assertRaisesRegex(ValueError,"no registered job"):
                C.execute(IDENT)
    def test_service_requires_immutable_release_at_install_time(self):
        self.assertIn("@IMMUTABLE_RELEASE_DIR@",self.unit)
        self.assertNotIn("/runtime/reasonpack/current",self.unit)
        self.assertIn("ReadWritePaths=/srv/ghostmesh/workspaces/runs/reasonpack-jobs/%i",self.unit)

    def test_owner_prestart_is_one_exact_audited_root_command(self):
        self.assertIn("ExecStartPre=+/usr/bin/python3 @IMMUTABLE_RELEASE_DIR@/ops/acquisition-owner-prestart.py --job-id %i",self.unit)
        for replacement in ("ExecStartPre=+/bin/sh",
                            "ExecStartPre=/usr/bin/python3",
                            "ExecStartPre=-+/usr/bin/python3"):
            with self.subTest(replacement=replacement),self.assertRaisesRegex(
                    ValueError,"one-time grant claim"):
                C.verify_install_contract(self.unit.replace(
                  "ExecStartPre=+/usr/bin/python3",replacement))
    def test_never_add_second_listener_or_email_dispatch_to_unit(self):
        for forbidden in ("ghostmesh-commons-responder","gmail","slack","mail-current","ExecStopPost="):
            self.assertNotIn(forbidden,self.unit)
        self.assertEqual(self.unit.count("ExecStartPre="),1)
        self.assertNotIn("Delegate=yes",self.unit)

if __name__=="__main__":unittest.main(verbosity=2)
