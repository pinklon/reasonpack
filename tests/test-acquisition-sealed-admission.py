#!/usr/bin/env python3
"""Linux sealed-memfd regression: child must consume only approved bytes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("rp_memfd_under_test",
  ROOT/"ops/acquisition-sealed-admission.py")
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

class FrozenAdmissionTests(unittest.TestCase):
    def test_signed_snapshot_survives_worker_writable_disk_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            job=Path(d)/"admission.json"
            correct=b'{"video_id":"ZhM29Ds-mBg","job_id":"original"}\n'
            forged=b'{"video_id":"XXXXXXXXXXX","job_id":"original"}\n'
            job.write_bytes(correct)
            fd=M.seal_admission(job.read_bytes())
            self.addCleanup(lambda: os.close(fd))
            # Attack changes the real disk admission after the parent
            # has sealed it, before the worker selects a source.
            job.write_bytes(forged)
            self.assertNotEqual(correct,job.read_bytes())
            self.assertEqual(M.read_sealed_admission(fd),correct)
            self.assertNotIn(b"XXXXXXXXXXX",M.read_sealed_admission(fd))
    def test_sealed_descriptor_cannot_be_written_by_child(self):
        raw=b'{"video_id":"ZhM29Ds-mBg"}'
        fd=M.seal_admission(raw)
        try:
            code='''import os,sys
n=int(sys.argv[1])
try:
 os.lseek(n,0,0);os.write(n,b"forgery")
except OSError:
 pass
else:
 raise SystemExit("ERR: sealed admission was writable")
os.lseek(n,0,0)
assert os.read(n,100)==b'{"video_id":"ZhM29Ds-mBg"}'
print("CHILD_SEALED_READ_OK")
'''
            proc=subprocess.run([sys.executable,"-c",code,str(fd)],
                 pass_fds=(fd,),capture_output=True,text=True,timeout=5)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn("CHILD_SEALED_READ_OK",proc.stdout)
        finally:os.close(fd)
    def test_unsealed_file_and_pipe_are_rejected(self):
        with tempfile.TemporaryFile() as f:
            f.write(b"pretend-signed-admission");f.flush()
            with self.assertRaises((ValueError,OSError)):
                M.read_sealed_admission(f.fileno())
        r,w=os.pipe()
        try:
            with self.assertRaises((ValueError,OSError)):
                M.read_sealed_admission(r)
        finally:
            os.close(r);os.close(w)
    def test_source_stays_bound_to_admission_fd_not_disk(self):
        child=(ROOT/"ops/acquisition-real-worker.py").read_text()
        parent=(ROOT/"ops/acquisition-cgroup-runner.py").read_text()
        self.assertIn('sealed.read_sealed_admission(args.admission_fd)',child)
        self.assertNotIn('source=mod.validate_admission((args.job/"admission.json").read_bytes())',child)
        self.assertIn('"--admission-fd",str(sealed_fd)',parent)
        self.assertIn("pass_fds=(rfd,sealed_fd)",parent)
        self.assertLess(parent.index("custody.verify_for_job"),
                        parent.index("handoff.seal_admission(raw_admission)"))
        self.assertLess(parent.index("handoff.seal_admission(raw_admission)"),
                        parent.index("os.write(wfd,b"+'"G"'+")"))
    def test_supervision_json_state_uses_actual_newline(self):
        # The parent writes twice: launch intent and running state. Both
        # receipts MUST be parseable JSON, not JSON followed by literal \\n.
        import ast
        src=(ROOT/"ops/acquisition-cgroup-runner.py").read_text()
        constants=[n.value for n in ast.walk(ast.parse(src))
                   if isinstance(n,ast.Constant) and isinstance(n.value,str)]
        self.assertGreaterEqual(constants.count("\n"),2)
        self.assertNotIn("\\n",constants)
        record={"status":"running","job_id":"a"*64}
        original=(json.dumps(record,sort_keys=True,indent=2)+"\n").encode()
        self.assertEqual(json.loads(original),record)

    def test_refuse_empty_or_oversized_snapshot(self):
        for raw in (b"",b"a"*(M.MAX_BYTES+1)):
            with self.assertRaises(ValueError):
                M.seal_admission(raw)
    def test_fd_seals_guard_against_inplace_modification(self):
        fd=M.seal_admission(b"immutable")
        try:
            self.assertEqual(M.assert_sealed(fd),9)
            with self.assertRaises(OSError):
                os.write(fd,b"!")
            self.assertEqual(M.read_sealed_admission(fd),b"immutable")
        finally:os.close(fd)

if __name__=="__main__":unittest.main(verbosity=2)
