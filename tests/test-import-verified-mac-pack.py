#!/usr/bin/env python3
"""Offline tests for provenance-preserving macOS ReasonPack import."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("mac_import",ROOT/"ops/import-verified-mac-pack.py")
importer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)
VIDEO="ZhM29Ds-mBg"

def hashed(raw):
    return hashlib.sha256(raw).hexdigest()

def fixture(path):
    path.mkdir()
    files={
        "video.mp4":b"synthetic bytes, not media",
        "audio.m4a":b"synthetic bytes, not audio",
        "transcript.srt":b"1\n00:00:00,000 --> 00:00:01,000\nA synthetic test\n",
        "transcript.txt":b"[00:00:00] A synthetic test\n",
        "REASONING.md":b"Fixture only, do not publish\n",
    }
    for name,raw in files.items():(path/name).write_bytes(raw)
    source={"schema":"reasonpack/1.0","source":{"type":"youtube","url":"https://www.youtube.com/watch?v="+VIDEO,
        "video_id":VIDEO,"title":"Synthetic fixture","channel":"Test Channel"},
        "transcript":{"status":"captions","language_prefix":"en"},
        "files":[{"name":n,"sha256":hashed(files[n]),"bytes":len(files[n])} for n in
            ("video.mp4","audio.m4a","transcript.srt","transcript.txt")]}
    (path/"manifest.json").write_text(json.dumps(source,indent=2)+"\n")
    members=["video.mp4","audio.m4a","transcript.srt","transcript.txt","manifest.json","REASONING.md"]
    (path/"SHA256SUMS.txt").write_text("".join(importer.digest(path/n)+"  "+n+"\n" for n in members))
    return path

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.src=fixture(self.dir/"original")
        self.out=self.dir/"canonical"
    def test_valid_original_custody(self):
        manifest,url,proof=importer.verify_original(self.src)
        self.assertEqual(url,"https://www.youtube.com/watch?v="+VIDEO)
        self.assertEqual(proof["video.mp4"],importer.digest(self.src/"video.mp4"))
    def test_canonical_import_preserves_bytes_and_marks_origin(self):
        real_run=subprocess.run
        def instrumented(cmd,*args,**kwargs):
            if cmd[0]=="ffprobe":
                return SimpleNamespace(returncode=0,stdout=b'{"streams":[],"format":{}}')
            return real_run(cmd,*args,**kwargs)
        with mock.patch.object(importer.subprocess,"run",side_effect=instrumented):
            importer.import_pack(self.src,self.out,ROOT/"bin/reasonpack")
        self.assertTrue(self.out.exists())
        canonical=json.loads((self.out/"manifest.json").read_text())
        self.assertFalse(canonical["importedFrom"]["freshProviderRetrieval"])
        self.assertEqual(json.loads((self.out/"source.json").read_text())["fresh_youtube_download"],False)
        for name in ("video.mp4","audio.m4a","transcript.txt","transcript.srt"):
            self.assertEqual(importer.digest(self.src/name),importer.digest(self.out/name))
        self.assertEqual(real_run([str(ROOT/"bin/reasonpack"),"verify",str(self.out)],
                     capture_output=True,text=True).returncode,0)
        with self.assertRaises(ValueError):
            importer.import_pack(self.src,self.out,ROOT/"bin/reasonpack")
    def test_tampered_media_rejected(self):
        (self.src/"audio.m4a").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"integrity failure"):
            importer.verify_original(self.src)
    def test_tampered_manifest_rejected(self):
        m=json.loads((self.src/"manifest.json").read_text())
        m["source"]["video_id"]="jNQXAC9IVRw"
        (self.src/"manifest.json").write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            importer.verify_original(self.src)
    def test_mutation_during_source_copy_is_rejected(self):
        actual_copy=importer.shutil.copyfile
        def mutating_copy(source,target):
            source=Path(source)
            if source.name=="manifest.json":
                source.write_text(source.read_text()+" ")
            return actual_copy(source,target)
        with mock.patch.object(importer.shutil,"copyfile",side_effect=mutating_copy):
            with self.assertRaisesRegex(ValueError,"verified original source changed"):
                importer.import_pack(self.src,self.out,ROOT/"bin/reasonpack")
        self.assertFalse(self.out.exists())

    def test_nested_destination_does_not_mutate_source(self):
        nested=self.src/"derived"/"canonical"
        with self.assertRaisesRegex(ValueError,"outside the verified source"):
            importer.import_pack(self.src,nested,Path(__file__))
        self.assertFalse((self.src/"derived").exists())
        importer.verify_original(self.src)

    def test_extra_file_rejected(self):
        (self.src/"extra.bin").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError,"untracked"):
            importer.verify_original(self.src)
    def test_symlink_member_rejected(self):
        (self.src/"audio.m4a").unlink()
        (self.src/"audio.m4a").symlink_to(self.src/"video.mp4")
        with self.assertRaises(ValueError):
            importer.verify_original(self.src)
    def test_source_manifest_conflicting_hash_rejected(self):
        m=json.loads((self.src/"manifest.json").read_text())
        m["files"][0]["sha256"]="a"*64
        (self.src/"manifest.json").write_text(json.dumps(m))
        (self.src/"SHA256SUMS.txt").write_text("".join(importer.digest(self.src/n)+"  "+n+"\n" for n in
             ("video.mp4","audio.m4a","transcript.srt","transcript.txt","manifest.json","REASONING.md")))
        with self.assertRaisesRegex(ValueError,"disagrees"):
            importer.verify_original(self.src)

if __name__=="__main__":
    unittest.main(verbosity=2)
