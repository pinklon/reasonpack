#!/usr/bin/env python3
"""Adversarial, offline non-root regression for privileged owner file reads."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"ops/acquisition-safe-owner-io.py"
spec=importlib.util.spec_from_file_location("rp_safe_owner_io_tests",p)
IO=importlib.util.module_from_spec(spec);spec.loader.exec_module(IO)
ID="a"*64

class SafeReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent=Path(self.tmp.name)/"jobs"
        self.parent.mkdir(mode=0o700)
        self.job=self.parent/ID
        self.job.mkdir(mode=0o700)
        (self.job/"admission.json").write_bytes(b'{"schema":"safe-test"}')
    def test_reads_only_pinned_regular_file(self):
        with IO._open_tree_dir(self.parent,ID) as fd:
            self.assertEqual(IO.read_regular_member(fd,"admission.json",256),
                             b'{"schema":"safe-test"}')
    def test_symlink_to_sensitive_file_refused(self):
        (self.job/"admission.json").unlink()
        (self.job/"admission.json").symlink_to("/etc/passwd")
        with IO._open_tree_dir(self.parent,ID) as fd:
            with self.assertRaises(OSError):
                IO.read_regular_member(fd,"admission.json",256)
    def test_oversize_payload_refused_before_allocation(self):
        (self.job/"admission.json").write_bytes(b"Z"*1024)
        with IO._open_tree_dir(self.parent,ID) as fd:
            with self.assertRaisesRegex(ValueError,"oversized"):
                IO.read_regular_member(fd,"admission.json",128)
    def test_fifo_does_not_block_root(self):
        (self.job/"admission.json").unlink()
        os.mkfifo(self.job/"admission.json")
        with IO._open_tree_dir(self.parent,ID) as fd:
            with self.assertRaisesRegex(ValueError,"nonregular"):
                IO.read_regular_member(fd,"admission.json",256)
    def test_directory_member_cannot_be_read(self):
        (self.job/"supervision.json").mkdir()
        with IO._open_tree_dir(self.parent,ID) as fd:
            with self.assertRaises((ValueError,OSError)):
                IO.read_regular_member(fd,"supervision.json",256)
    def test_symlinked_job_or_parent_rejected(self):
        link=self.parent/("b"*64)
        link.symlink_to(self.job,target_is_directory=True)
        with self.assertRaises(OSError):
            with IO._open_tree_dir(self.parent,"b"*64):pass
        base=Path(self.tmp.name)/"substitute"
        base.symlink_to(self.parent,target_is_directory=True)
        with self.assertRaises(OSError):
            with IO._open_tree_dir(base,ID):pass
    def test_pinned_fd_survives_directory_rename_without_redirect(self):
        with IO._open_tree_dir(self.parent,ID) as fd:
            self.job.rename(self.parent/("x"*64))
            self.job.mkdir(mode=0o700)
            (self.job/"admission.json").write_bytes(b"ATTACKER_REPLACEMENT")
            self.assertEqual(IO.read_regular_member(fd,"admission.json",256),
                             b'{"schema":"safe-test"}')
    def test_only_four_fixed_member_names_accepted(self):
        with IO._open_tree_dir(self.parent,ID) as fd:
            for name in (".ssh/id_ed25519","../admission.json",
                         "/etc/passwd","whatever","admission.json/../x"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError,"unapproved"):
                    IO.read_regular_member(fd,name,256)
    def test_root_helper_uses_snapshot_bytes_instead_of_paths(self):
        code=(ROOT/"ops/acquisition-owner-prestart.py").read_text()
        self.assertIn("safe.opened_job(job_id)",code)
        self.assertIn('safe.read_regular_member(jobfd,"admission.json",40_000)',code)
        self.assertIn('safe.read_regular_member(jobfd,"supervision.json",65_536)',code)
        self.assertIn('safe.read_regular_member(jobfd,"launch-grant.json",8_192)',code)
        self.assertIn('safe.read_regular_member(jobfd,"launch-grant.sig",4_096)',code)
        owner=code.split("def prestart(job_id):",1)[1].split("def main():",1)[0]
        self.assertNotIn("guard.state(",owner)
        self.assertNotIn("signed.verify_for_job(",owner)
        self.assertIn("signed.verify_from_bytes(",owner)
    def test_prod_entrypoint_has_fixed_root_and_strict_id(self):
        self.assertEqual(str(IO.JOB_ROOT),"/srv/ghostmesh/workspaces/runs/reasonpack-jobs")
        with self.assertRaisesRegex(ValueError,"unsafe root job locator"):
            with IO.opened_job("../foo"): pass
        with self.assertRaisesRegex(ValueError,"unsafe root job locator"):
            with IO.opened_job("z"*64): pass

if __name__=="__main__": unittest.main(verbosity=2)
