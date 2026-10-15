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
                stdout.write(json.dumps({"id":"jEOUUAPC1sc","is_live":False,
                  "subtitles":{"en-orig":[{"ext":"vtt"}],"en":[{"ext":"vtt"}]}}).encode())
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
        self.assertEqual(meta["last_caption_second"],30.0)
        self.assertIn(b"Another idea.",txt)
        with self.assertRaisesRegex(ValueError,"not WebVTT"):
            M.timed_vtt(b"not captions")
    def test_regional_english_captions_complete_canonical_package(self):
        def regional_runner(argv,*,stdout=None):
            if "--dump-single-json" in argv:
                self.calls.append(argv)
                stdout.write(json.dumps({"id":"jEOUUAPC1sc","is_live":False,
                    "automatic_captions":{"en-US":[{"ext":"vtt"}]}}).encode())
                return
            self.fake_run(argv,stdout=stdout)
            if "--write-subs" in argv:
                template=Path(argv[argv.index("-o")+1])
                for name in ("captions.en-orig.vtt","captions.en.vtt"):
                    template.with_name(name).unlink()
                template.with_name("captions.en-US.vtt").write_bytes(VTT)
        result=M.build(URL,self.tmp/"regional",run=regional_runner,
                       probe_media=self.fake_probe)
        self.assertEqual(result["status"],"canonical-direct-remux-verified")
        self.assertEqual((self.tmp/"regional/captions.vtt").read_bytes(),VTT)
        names={p.name for p in (self.tmp/"regional").iterdir()}
        self.assertNotIn("captions.en-US.vtt",names)
        self.assertTrue(any("--sub-langs" in c and c[c.index("--sub-langs")+1]=="en-US"
                            for c in self.calls if c[0]=="yt-dlp"))

    def test_unused_regional_fallback_is_not_downloaded(self):
        def runner(argv,*,stdout=None):
            if "--dump-single-json" in argv:
                self.calls.append(argv)
                stdout.write(json.dumps({"id":"jEOUUAPC1sc",
                  "automatic_captions":{"en-orig":[{"ext":"vtt"}],
                                        "en-GB":[{"ext":"vtt"}]}}).encode())
                return
            if "--sub-langs" in argv and argv[argv.index("--sub-langs")+1]=="en-GB":
                self.fail("Unused regional fallback must not be downloaded")
            self.fake_run(argv,stdout=stdout)
        got=M.build(URL,self.tmp/"preferred",run=runner,probe_media=self.fake_probe)
        self.assertEqual(got["status"],"canonical-direct-remux-verified")
        langs=[c[c.index("--sub-langs")+1] for c in self.calls
               if c[0]=="yt-dlp" and "--sub-langs" in c]
        self.assertEqual(langs,["en-orig"])

    def test_original_track_failure_falls_back_to_english(self):
        def runner(argv,*,stdout=None):
            if ("--sub-langs" in argv
                 and argv[argv.index("--sub-langs")+1]=="en-orig"):
                self.calls.append(argv)
                raise subprocess.CalledProcessError(1,argv)
            self.fake_run(argv,stdout=stdout)
        got=M.build(URL,self.tmp/"fallback",run=runner,probe_media=self.fake_probe)
        self.assertEqual(got["status"],"canonical-direct-remux-verified")
        langs=[c[c.index("--sub-langs")+1] for c in self.calls
               if c[0]=="yt-dlp" and "--sub-langs" in c]
        self.assertEqual(langs,["en-orig","en"])

    def test_overlapping_webvtt_cues_are_valid_and_counted(self):
        clip=(b"WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n"
              b"Long first cue.\n\n00:00:02.000 --> 00:00:05.000\n"
              b"Short overlapping cue.\n")
        transcript,state=M.timed_vtt(clip)
        self.assertEqual(state["last_caption_second"],10.0)
        self.assertEqual(state["source_cue_count"],2)
        self.assertIn(b"Short overlapping cue.",transcript)
        invalid=(b"WEBVTT\n\n00:00:02.000 --> 00:00:05.000\nOne.\n\n"
                 b"00:00:01.000 --> 00:00:03.000\nTwo.\n")
        with self.assertRaisesRegex(ValueError,"out-of-order"):
            M.timed_vtt(invalid)

    def test_timestamp_without_hours_is_supported(self):
        cue=(b"WEBVTT\n\n001\n00:00.000 --> 00:03.000\n"
             b"First line.\n\n002\n01:20.000 --> 02:00.000\n"
             b"Final line.\n")
        text,meta=M.timed_vtt(cue)
        self.assertEqual(meta["last_caption_second"],120.0)
        self.assertEqual(text,b"First line.\nFinal line.\n")

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

    def test_caption_end_coverage_and_numbered_cue_identifiers(self):
        cues=(b"WEBVTT\n\n001\n00:00:00.000 --> 00:00:15.000\n"
              b"Spoken content.\n\nclip-002\n"
              b"00:01:20.000 --> 00:02:00.000\nFinal sentence.\n")
        transcript,meta=M.timed_vtt(cues)
        self.assertEqual(meta["last_caption_second"],120.0)
        self.assertEqual(meta["source_cue_count"],2)
        self.assertNotIn(b"001",transcript)
        self.assertNotIn(b"clip-002",transcript)
        self.assertEqual(transcript,b"Spoken content.\nFinal sentence.\n")
        self.assertGreaterEqual(meta["last_caption_second"],120-max(25,120*0.02))

    def test_fast_builder_does_not_change_legacy_build(self):
        source=(ROOT/"bin/reasonpack").read_text()
        self.assertIn("build-fast)",source)
        self.assertIn("build) [[ $# -eq 2 ]] || exit 64; build",source)
        self.assertIn("-c:v libx264",source)  # existing compatibility path retained
        self.assertNotIn("RuntimeMaxSec=7200",(ROOT/"ops/direct-remux-pack.py").read_text())

if __name__=="__main__":unittest.main(verbosity=2)
