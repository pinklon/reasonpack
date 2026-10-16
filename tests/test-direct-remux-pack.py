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
VIDEO={"streams":[{"codec_type":"video","codec_name":"av1","duration":"30.5"},
                  {"codec_type":"audio","codec_name":"aac","duration":"30.5"}],
       "format":{"duration":"30.5"}}
AUDIO={"streams":[{"codec_type":"audio","codec_name":"aac","duration":"30.5"}],
       "format":{"duration":"30.5"}}
VTT=b"WEBVTT\nKind: captions\nLanguage: en\n\n00:00:00.000 --> 00:00:03.000\nHello from Argon.\n\n00:00:27.000 --> 00:00:30.000\nAnother idea.\n"
VERSIONS={"yt-dlp":"2026.08.19","ffmpeg":"ffmpeg version 8.0",
          "ffprobe":"ffprobe version 8.0","python3":"Python 3.14.4"}

class DirectPackTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp=Path(t.name)
        self.calls=[]
    def build_fast(self,target,*,run,probe_media):
        return M.build(URL,target,run=run,probe_media=probe_media,
                       version_reader=lambda:VERSIONS)
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
        res=self.build_fast(target,run=self.fake_run,probe_media=self.fake_probe)
        self.assertEqual(res["status"],"canonical-direct-remux-verified")
        self.assertFalse(res["video_reencoded"])
        self.assertEqual(res["video_codec"],"av1")
        self.assertEqual(res["video_id"],"jEOUUAPC1sc")
        m=json.loads((target/"manifest.json").read_text())
        self.assertEqual(m["mediaPreparation"],"direct-mp4-aac-remux-no-video-encode")
        self.assertEqual(len(m["members"]),7)
        self.assertEqual(m["tools"],VERSIONS)
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
            self.build_fast(t,run=self.fake_run,probe_media=self.fake_probe)
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
    def test_short_video_stream_fails_even_when_container_and_audio_match(self):
        from copy import deepcopy
        video=deepcopy(VIDEO)
        audio=deepcopy(AUDIO)
        video["streams"][0]["duration"]="15.0"
        # Both MP4 and M4A container durations still report 30.5 seconds.
        with self.assertRaisesRegex(ValueError,"stream durations disagree"):
            M.validate_direct_media(self.tmp/"video.mp4",self.tmp/"audio.m4a",
                                    video,audio)

    def test_short_media_stream_cannot_pass_with_complete_container_and_audio(self):
        from copy import deepcopy
        video_path=self.tmp/"video.mp4"
        audio_path=self.tmp/"audio.m4a"
        video_path.write_bytes(b"video-fixture")
        audio_path.write_bytes(b"audio-fixture")
        cases=((20.0,15.1,False),(20.0,19.9,True),
               (30.5,25.6,False),(30.5,30.4,True),
               (1850.0,1844.0,False),(1850.0,1846.0,True))
        for duration,actual_stream,accepted in cases:
            with self.subTest(container=duration,video_stream=actual_stream):
                video=deepcopy(VIDEO)
                audio=deepcopy(AUDIO)
                video["format"]["duration"]=str(duration)
                for stream in video["streams"]:
                    stream["duration"]=str(duration)
                video["streams"][0]["duration"]=str(actual_stream)
                audio["format"]["duration"]=str(duration)
                audio["streams"][0]["duration"]=str(duration)
                if accepted:
                    got=M.validate_direct_media(video_path,audio_path,video,audio)
                    self.assertEqual(got["duration_seconds"],duration)
                else:
                    with self.assertRaisesRegex(ValueError,"stream durations disagree"):
                        M.validate_direct_media(video_path,audio_path,video,audio)
        for nonfinite in ("nan","inf","-inf"):
            video=deepcopy(VIDEO)
            video["streams"][0]["duration"]=nonfinite
            with self.subTest(nonfinite=nonfinite):
                with self.assertRaisesRegex(ValueError,"invalid video/audio stream duration"):
                    M.validate_direct_media(video_path,audio_path,video,AUDIO)

    def test_complete_captions_cannot_mask_truncated_short_video(self):
        from copy import deepcopy
        video=deepcopy(VIDEO)
        audio=deepcopy(AUDIO)
        video["format"]["duration"]="20.0"
        video["streams"][0]["duration"]="15.1"
        video["streams"][1]["duration"]="20.0"
        audio["format"]["duration"]="20.0"
        audio["streams"][0]["duration"]="20.0"
        target=self.tmp/"truncated-media"
        def short_probe(path):
            return video if Path(path).name=="video.mp4" else audio
        with self.assertRaisesRegex(ValueError,"stream durations disagree"):
            self.build_fast(target,run=self.fake_run,probe_media=short_probe)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.tmp.glob(".reasonpack-fast-stage-*")))

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
        result=self.build_fast(self.tmp/"regional",run=regional_runner,
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
        got=self.build_fast(self.tmp/"preferred",run=runner,probe_media=self.fake_probe)
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
        got=self.build_fast(self.tmp/"fallback",run=runner,probe_media=self.fake_probe)
        self.assertEqual(got["status"],"canonical-direct-remux-verified")
        langs=[c[c.index("--sub-langs")+1] for c in self.calls
               if c[0]=="yt-dlp" and "--sub-langs" in c]
        self.assertEqual(langs,["en-orig","en"])

    def test_empty_trailing_cues_do_not_claim_full_transcript_coverage(self):
        caption=(b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n"
                 b"Actual spoken words.\n\n"
                 b"00:01:55.000 --> 00:02:00.000\n<c></c>\n")
        out,metadata=M.timed_vtt(caption)
        self.assertEqual(metadata["source_cue_count"],2)
        self.assertEqual(metadata["last_caption_second"],2.0)
        self.assertEqual(out,b"Actual spoken words.\n")
        self.assertLess(metadata["last_caption_second"],120-max(25,120*0.02))

    def test_repeated_speech_after_a_pause_is_preserved(self):
        spoken=(b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nNo\n\n"
                b"00:00:10.000 --> 00:00:11.000\nNo new taxes\n")
        text,_=M.timed_vtt(spoken)
        self.assertEqual(text,b"No\nNo new taxes\n")

    def test_corrupt_preferred_caption_falls_back_to_valid_english(self):
        def runner(argv,*,stdout=None):
            self.fake_run(argv,stdout=stdout)
            if ("--sub-langs" in argv and
                argv[argv.index("--sub-langs")+1]=="en-orig"):
                template=Path(argv[argv.index("-o")+1])
                template.with_name("captions.en-orig.vtt").write_bytes(
                    b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\ntruncated\n")
        got=self.build_fast(self.tmp/"verified-fallback",run=runner,
                    probe_media=self.fake_probe)
        self.assertEqual(got["status"],"canonical-direct-remux-verified")
        self.assertEqual((self.tmp/"verified-fallback/captions.vtt").read_bytes(),VTT)
        langs=[c[c.index("--sub-langs")+1] for c in self.calls
               if c[0]=="yt-dlp" and "--sub-langs" in c]
        self.assertEqual(langs,["en-orig","en"])

    def test_rolling_caption_overlap_is_removed_without_dropping_new_words(self):
        cues=(b"WEBVTT\n\n00:00:00.000 --> 00:00:03.000\n"
              b"I have used Gemini\n\n"
              b"00:00:03.000 --> 00:00:05.000\n"
              b"I have used Gemini\nfor Argon\n\n"
              b"00:00:05.000 --> 00:00:07.000\n"
              b"for Argon\nfor the last seven days\n")
        transcript,record=M.timed_vtt(cues)
        self.assertEqual(record["source_cue_count"],3)
        self.assertEqual(transcript,
                         b"I have used Gemini\nfor Argon\nfor the last seven days\n")
        duplicates=(b"WEBVTT\n\n00:00:00.000 --> 00:00:03.000\nA\nB\n\n"
                    b"00:00:03.000 --> 00:00:05.000\nA\nB\nC\n")
        normalized,_=M.timed_vtt(duplicates)
        self.assertEqual(normalized,b"A B\nC\n")

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

    def test_short_video_caption_tolerance_is_duration_relative(self):
        cases=((20.0,1.0,False),(30.0,5.0,False),
               (20.0,19.5,True),(30.0,29.0,True),
               (30.5,30.0,True),(1850.0,1826.0,True),
               (1850.0,1824.0,False),(2.0,0.1,False),
               (2.0,1.95,True),(20.0,25.0,False))
        for duration,last,expected in cases:
            with self.subTest(duration=duration,last=last):
                self.assertEqual(M.captions_reach_end(last,duration),expected)
        for invalid in (float("nan"),float("inf"),-1.0,0.0):
            self.assertFalse(M.captions_reach_end(invalid,30.0))
            self.assertFalse(M.captions_reach_end(1.0,invalid))

    def test_truncated_short_video_captions_cannot_publish_pack(self):
        from copy import deepcopy
        short_video=deepcopy(VIDEO)
        short_audio=deepcopy(AUDIO)
        for track in short_video["streams"]:
            track["duration"]="20.0"
        short_video["format"]["duration"]="20.0"
        short_audio["streams"][0]["duration"]="20.0"
        short_audio["format"]["duration"]="20.0"
        truncated=(b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n"
                   b"Incomplete caption.\n")
        self.assertEqual(M.timed_vtt(truncated)[1]["last_caption_second"],1.0)
        def runner(argv,*,stdout=None):
            self.fake_run(argv,stdout=stdout)
            if "--write-subs" in argv:
                template=Path(argv[argv.index("-o")+1])
                for suffix in ("en-orig","en"):
                    template.with_name("captions."+suffix+".vtt").write_bytes(truncated)
        def probe_short(path):
            return short_video if Path(path).name=="video.mp4" else short_audio
        target=self.tmp/"short-incomplete"
        with self.assertRaisesRegex(ValueError,"no usable full-length English captions"):
            self.build_fast(target,run=runner,probe_media=probe_short)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.tmp.glob(".reasonpack-fast-stage-*")))

    def test_tool_provenance_capture_and_fail_closed(self):
        seen=[]
        def tool_runner(argv,**kwargs):
            seen.append(argv)
            self.assertEqual(kwargs["timeout"],10)
            self.assertEqual(kwargs["stdin"],subprocess.DEVNULL)
            return subprocess.CompletedProcess(argv,0,VERSIONS[argv[0]].encode()+b"\n")
        self.assertEqual(M.capture_tool_versions(runner=tool_runner),VERSIONS)
        self.assertEqual(seen,[["yt-dlp","--version"],["ffmpeg","-version"],
                               ["ffprobe","-version"],["python3","--version"]])
        for code,payload in ((1,b"error"),(0,b""),(0,b"X"*65537)):
            def rejected_runner(argv,**kwargs):
                return subprocess.CompletedProcess(argv,code,payload)
            with self.subTest(code=code,output_bytes=len(payload)):
                with self.assertRaisesRegex(ValueError,"tool version unavailable"):
                    M.capture_tool_versions(runner=rejected_runner)

    def test_fast_builder_does_not_change_legacy_build(self):
        source=(ROOT/"bin/reasonpack").read_text()
        self.assertIn("build-fast)",source)
        self.assertIn("build) [[ $# -eq 2 ]] || exit 64; build",source)
        self.assertIn("-c:v libx264",source)  # existing compatibility path retained
        self.assertNotIn("RuntimeMaxSec=7200",(ROOT/"ops/direct-remux-pack.py").read_text())

if __name__=="__main__":unittest.main(verbosity=2)
