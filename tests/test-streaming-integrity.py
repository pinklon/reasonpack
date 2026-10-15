#!/usr/bin/env python3
"""No-network bounded-memory media integrity regression checks."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/"bin/reasonpack"
BYTES=128*1024*1024+17
LIMIT=72*1024*1024

def sha_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def limited_memory():
    resource.setrlimit(resource.RLIMIT_AS,(LIMIT,LIMIT))

def build_pack(directory):
    directory.mkdir()
    src=ROOT/"examples/sample-reasonpack"
    for p in src.iterdir():
        if p.is_file():
            shutil.copyfile(p,directory/p.name)
    video=directory/"video.mp4"
    with video.open("wb") as fp:
        fp.truncate(BYTES)  # sparse media-shaped bytes; NOT a playable video
        fp.seek(BYTES-1)
        fp.write(b"Z")
    m=json.loads((directory/"manifest.json").read_text())
    for item in m["members"]:
        file=directory/item["path"]
        item["bytes"]=file.stat().st_size
        item["sha256"]=sha_file(file)
    (directory/"manifest.json").write_text(json.dumps(m,sort_keys=True,indent=2)+"\n")
    names=[x["path"] for x in m["members"]]+["manifest.json"]
    (directory/"SHA256SUMS.txt").write_text("".join(
       sha_file(directory/name)+"  "+name+"\n" for name in names))
    return m

def verify(directory):
    return subprocess.run([str(CLI),"verify",str(directory)],
       capture_output=True,text=True,timeout=90,preexec_fn=limited_memory)

class StreamingIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pack=Path(self.tmp.name)/"synthetic"
    def test_large_sparse_file_verifies_in_small_memory(self):
        build_pack(self.pack)
        self.assertGreater((self.pack/"video.mp4").stat().st_size,LIMIT)
        result=verify(self.pack)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("PASS reasoning pack verification",result.stdout)
    def test_one_byte_changed_near_end_rejected(self):
        build_pack(self.pack)
        with (self.pack/"video.mp4").open("r+b") as f:
            f.seek(BYTES-2)
            f.write(b"x")
        self.assertNotEqual(verify(self.pack).returncode,0)
    def test_misreported_member_length_rejected(self):
        m=build_pack(self.pack)
        for row in m["members"]:
            if row["path"]=="video.mp4":row["bytes"]+=10
        (self.pack/"manifest.json").write_text(json.dumps(m))
        self.assertNotEqual(verify(self.pack).returncode,0)
    def test_sha_inventory_tampering_rejected(self):
        build_pack(self.pack)
        f=self.pack/"SHA256SUMS.txt"
        f.write_text(f.read_text().replace("video.mp4","unrelated.mp4"))
        self.assertNotEqual(verify(self.pack).returncode,0)
    def test_no_whole_media_read_regression(self):
        code=CLI.read_text()
        self.assertNotIn("hashlib.sha256(open(p,'rb').read())",code)
        self.assertGreaterEqual(code.count("for part in iter(lambda:f.read(1024*1024)"),3)
    def test_symbolic_link_member_is_not_trusted(self):
        shutil.copytree(ROOT/"examples/sample-reasonpack",self.pack)
        real=self.pack.parent/"outside-verified-bytes.mp4"
        original=self.pack/"video.mp4"
        original.rename(real)
        original.symlink_to(real)
        p=verify(self.pack)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("linked member",p.stderr)

    def test_traversal_member_path_rejected_before_read(self):
        shutil.copytree(ROOT/"examples/sample-reasonpack",self.pack)
        manifest=self.pack/"manifest.json"
        m=json.loads(manifest.read_text())
        m["members"][0]["path"]="../outside.mp4"
        manifest.write_text(json.dumps(m))
        p=verify(self.pack)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("unsafe member name",p.stderr)

    def test_duplicate_inventory_member_rejected(self):
        shutil.copytree(ROOT/"examples/sample-reasonpack",self.pack)
        inventory=self.pack/"SHA256SUMS.txt"
        line=inventory.read_text().splitlines()[0]
        inventory.write_text(inventory.read_text()+line+"\n")
        p=verify(self.pack)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("duplicate or untracked",p.stderr)

    def test_missing_inventory_member_rejected(self):
        shutil.copytree(ROOT/"examples/sample-reasonpack",self.pack)
        inventory=self.pack/"SHA256SUMS.txt"
        inventory.write_text("\n".join(inventory.read_text().splitlines()[:-1])+"\n")
        p=verify(self.pack)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("incomplete inventory",p.stderr)

    def test_existing_reference_pack(self):
        result=verify(ROOT/"examples/sample-reasonpack")
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=="__main__":
    unittest.main(verbosity=2)
