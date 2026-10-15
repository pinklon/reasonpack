#!/usr/bin/env python3
"""Offline tests for opt-in canonical direct-remux packs; never access YouTube."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("reasonpack_direct_remux",ROOT/"ops/direct-remux-pack.py")
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
URL="https://www.youtube.com/watch?v=jEOUUAPC1sc"
VIDEO={"streams":[{"codec_type":"video","codec_name":"av1"},
                  {"codec_type":"audio","codec_name":"aac"}],
       "format":{"duration":"30.5"}}
AUDIO={"streams":[{"codec_type":"audio","codec_name":"aac"}],
       "format":{"duration":"30.5"}}
VTT=b"WEBVTT\nKind: captions\nLanguage: en\n\n00:00:00.000 --> 00:00:03.000\nHello from Argon.\n\n00:00:27.000 --> 00:00:30.000\nAnother idea.\n"

class DirectPackTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp=Path(t.name)
        self.calls=[]
    def fake_run(self,argv,*,stdout=None):
        argv=list(map(str,argv))
        self.calls.append(argv)
        if argv[0]=="yt-dlp":
            self.assertIn("--ignore-config",argv)
            self.assertIn("--no-playlist",argv)
            if "--dump-single-json" in argv:
                stdout.write(json.dumps({"id":"jEOUUAPC1sc","is_live":False}).encode())
            elif "--write-subs" in argv:
                template=Path(argv[argv.index("-o")+1])
                p=template.with_name("captions.en-orig.vtt")
                p.write_bytes(VTT)
                template.with_name("captions.en.vtt").write_bytes(VTT)
            elif "-f" in argv:
                self.assertEqual(argv[argv.index("-f")+1],"bv*[ext=mp4]+ba[ext=m4a]")
                self.assertEqual(argv[argv.index("--merge-output-format")+1],"mp4")
                template=Path(argv[argv.index("-o")+1])
                template.with_name("video.mp4").write_bytes(b"FAKE_AV1_AAC_MEDIA")
            else:self.fail("Unexpected yt-dlp operation")
        elif argv[0]=="ffmpeg":
            self.assertEqual(argv[argv.index("-c:a")+1],"copy")
            self.assertNotIn("libx264",argv)
            self.assertNotIn("aac",argv) # codec name is not an encode directive
            Path(argv[-1]).write_bytes(b"FAKE_AAC_AUDIO")
        elif argv[0]==str(ROOT/"bin/reasonpack"):
            self.assertEqual(argv[1],"verify")
            p=subprocess.run(argv,check=True,capture_output=True,text=True,timeout=15)
            self.assertIn("PASS reasoning pack verification",p.stdout)
        else:self.fail("Unexpected command")
    def fake_probe(self,path):
        return VIDEO if Path(path).name=="video.mp4" else AUDIO
    def test_full_canonical_pack_without_reencode(self):
        target=self.tmp/"verified"
        res=M.build(URL,target,run=self.fake_run,probe_media=self.fake_probe)
        self.assertEqual(res["status"],"canonical-direct-remux-verified")
        self.assertFalse(res["video_reencoded"])
        self.assertEqual(res["video_codec"],"av1")
        self.assertEqual(res["video_id"],"jEOUUAPC1sc")
        m=json.loads((target/"manifest.json").read_text())
        self.assertEqual(m["mediaPreparation"],"direct-mp4-aac-remux-no-video-encode")
        self.assertEqual(len(m["members"]),7)
        self.assertIn("Hello from Argon.",(target/"transcript.txt").read_text())
        self.assertFalse(list(self.tmp.glob(".reasonpack-fast-stage-*")))
        self.assertEqual(sum(cmd[0]=="yt-dlp" for cmd in self.calls),3)
        result=subprocess.run([str(ROOT/"bin/reasonpack"),"verify",str(target)],
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_duplicate_destination_fails_before_external_calls(self):
        t=self.tmp/"already"
        t.mkdir()
        with self.assertRaisesRegex(ValueError,"exists"):
            M.build(URL,t,run=self.fake_run,probe_media=self.fake_probe)
        self.assertEqual(self.calls,[])
    def test_source_url_rejects_untrusted_hosts_and_parameters(self):
        for v in ("http://www.youtube.com/watch?v=jEOUUAPC1sc",
                  "https://youtube.com/watch?v=jEOUUAPC1sc",
                  "https://www.youtube.com/watch?v=jEOUUAPC1sc&evil=true",
                  "https://www.youtube.com/watch?v=1",
                  "https://www.youtube.com.evil.example/watch?v=jEOUUAPC1sc",
                  "https://www.youtube.com/watch?v=jEOUUAPC1sc#escape"):
            with self.subTest(url=v),self.assertRaises(ValueError):
                M.canonical_youtube(v)
    def test_invalid_media_codec_audio_and_duration_fail_closed(self):
        from copy import deepcopy
        for obj,atr in (({"streams":[{"codec_type":"video","codec_name":"vp9"},
                                      {"codec_type":"audio","codec_name":"aac"}],
                          "format":{"duration":"30.5"}},AUDIO),
                        (VIDEO,{"streams":[{"codec_type":"audio","codec_name":"opus"}],
                                "format":{"duration":"30.5"}}),
                        (VIDEO,{"streams":[{"codec_type":"audio","codec_name":"aac"}],
                                "format":{"duration":"20.0"}})):
            with self.subTest(data=obj),self.assertRaises(ValueError):
                M.validate_direct_media(self.tmp/"media",self.tmp/"audio",obj,atr)
    def test_caption_coverage_and_normalization(self):
        txt,meta=M.timed_vtt(VTT)
        self.assertEqual(meta["source_cue_count"],2)
        self.assertEqual(meta["last_caption_second"],27)
        self.assertIn(b"Another idea.",txt)
        with self.assertRaisesRegex(ValueError,"not WebVTT"):
            M.timed_vtt(b"not captions")
    def test_installed_alias_can_find_pinned_helper_without_network(self):
        import shutil
        installed=self.tmp/"share/reasonpack"
        scripts=self.tmp/"bin"
        installed.mkdir(parents=True)
        scripts.mkdir()
        shutil.copyfile(ROOT/"bin/reasonpack",installed/"reasonpack")
        shutil.copyfile(ROOT/"ops/direct-remux-pack.py",installed/"direct-remux-pack.py")
        (installed/"reasonpack").chmod(0o755)
        (scripts/"reasonpack").symlink_to(installed/"reasonpack")
        result=subprocess.run([str(scripts/"reasonpack"),"build-fast",
             "http://invalid.example/video",str(self.tmp/"should-not-create")],
             capture_output=True,text=True,timeout=8)
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertIn("canonical HTTPS YouTube URL",result.stderr)
        self.assertNotIn("helper not installed",result.stderr)
        self.assertFalse((self.tmp/"should-not-create").exists())

    def test_fast_builder_does_not_change_legacy_build(self):
        source=(ROOT/"bin/reasonpack").read_text()
        self.assertIn("build-fast)",source)
        self.assertIn("build) [[ $# -eq 2 ]] || exit 64; build",source)
        self.assertIn("-c:v libx264",source)  # existing compatibility path retained
        self.assertNotIn("RuntimeMaxSec=7200",(ROOT/"ops/direct-remux-pack.py").read_text())

if __name__=="__main__":unittest.main(verbosity=2)
