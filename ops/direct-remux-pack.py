#!/usr/bin/env python3
"""Private canonical ReasonPack builder using direct MP4/AAC remux.

No video re-encoding, credential or browser-cookie access, email, model or
publication. Explicit opt-in; the legacy full-transcode command is preserved.
If direct media is unavailable, fail closed instead of silently transcoding.
No arbitrary video-duration or total job-time cutoff is imposed.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
from html import unescape
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, parse_qs

ROOT=Path(__file__).resolve().parents[1]
VIDEO_ID=re.compile(r"^[A-Za-z0-9_-]{11}$")
VTT_TIME=r"(?:[0-9]{2}:)?[0-9]{2}:[0-9]{2}\.[0-9]{3}"
TIME=re.compile(r"^(?P<start>"+VTT_TIME+r") --> (?P<end>"+VTT_TIME+r")(?:\s|$)")

def vtt_seconds(value):
    fields=value.split(":")
    if len(fields)==2:
        minute,sec=fields
        return int(minute)*60+float(sec)
    hour,minute,sec=fields
    return int(hour)*3600+int(minute)*60+float(sec)
MEMBERS=("video.mp4","audio.m4a","transcript.txt","transcript-status.json",
         "source.json","ffprobe.json","captions.vtt")
MAX_SOURCE_JSON=8_000_000
MAX_VTT_BYTES=40_000_000

def hold(msg):raise ValueError(msg)

def canonical_youtube(url):
    if not isinstance(url,str) or len(url)>230:hold("invalid source URL")
    u=urlsplit(url)
    vid=parse_qs(u.query).get("v",[""])[0]
    if (u.scheme!="https" or u.hostname!="www.youtube.com" or
        u.path!="/watch" or u.username or u.password or u.port not in (None,443)
        or u.fragment or not VIDEO_ID.fullmatch(vid)
        or url!="https://www.youtube.com/watch?v="+vid):
        hold("one canonical HTTPS YouTube URL required")
    return vid

def file_sha(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def invoke(args,*,stdout=None):
    return subprocess.run(args,check=True,stdin=subprocess.DEVNULL,stdout=stdout)

def capture_tool_versions(*,runner=subprocess.run):
    versions={}
    for name in ("yt-dlp","ffmpeg","ffprobe","python3"):
        flag="-version" if name in ("ffmpeg","ffprobe") else "--version"
        result=runner([name,flag],stdin=subprocess.DEVNULL,
                      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                      timeout=10,check=False)
        output=result.stdout
        if (result.returncode!=0 or not isinstance(output,bytes)
            or not (0<len(output)<=65536)):
            hold("tool version unavailable: "+name)
        lines=output.decode("utf-8",errors="replace").splitlines()
        first=lines[0].strip() if lines else ""
        if not first or len(first)>1024:
            hold("invalid tool version: "+name)
        versions[name]=first
    return versions

def probe(path):
    p=subprocess.run(["ffprobe","-v","error","-show_streams",
         "-show_format","-of","json",str(path)],
         capture_output=True,text=True,timeout=45,check=True)
    if len(p.stdout)>4_000_000:hold("oversized ffprobe output")
    return json.loads(p.stdout)

def validate_direct_media(video,audio,video_probe,audio_probe):
    tracks=video_probe.get("streams",[])
    vc=[r.get("codec_name") for r in tracks if r.get("codec_type")=="video"]
    ac=[r.get("codec_name") for r in tracks if r.get("codec_type")=="audio"]
    if len(vc)!=1 or vc[0] not in ("av1","h264","hevc") or ac!=["aac"]:
        hold("MP4 must contain one supported video and one AAC track")
    ac2=[r.get("codec_name") for r in audio_probe.get("streams",[])
         if r.get("codec_type")=="audio"]
    if ac2!=["aac"] or any(r.get("codec_type")=="video"
                          for r in audio_probe.get("streams",[])):
        hold("extracted audio must be AAC-only")
    try:
        vd=float(video_probe["format"]["duration"])
        ad=float(audio_probe["format"]["duration"])
    except (ValueError,KeyError,TypeError):
        hold("media duration unavailable")
    try:
        actual_video=float(next(x["duration"] for x in tracks
                                if x.get("codec_type")=="video"))
        actual_audio=float(next(x["duration"] for x in tracks
                                if x.get("codec_type")=="audio"))
        extracted_audio=float(next(x["duration"] for x in audio_probe.get("streams",[])
                                   if x.get("codec_type")=="audio"))
    except (ValueError,KeyError,TypeError,StopIteration):
        hold("exact per-stream video/audio durations unavailable")
    durations=(vd,ad,actual_video,actual_audio,extracted_audio)
    if any(not math.isfinite(x) or x<=0 for x in durations):
        hold("invalid video/audio stream duration")
    # Short sources cannot lose seconds of visual evidence merely because the
    # MP4 container and AAC audio report the expected total duration.
    tolerance=min(5.0,max(0.25,vd*0.01),vd*0.05)
    if any(abs(x-actual_video)>tolerance for x in durations):
        hold("video/audio stream durations disagree")
    if any(not p.is_file() or p.is_symlink() or p.stat().st_size==0 for p in (video,audio)):
        hold("invalid direct media member")
    return {"video_codec":vc[0],"audio_codec":"aac","duration_seconds":vd}

def timed_vtt(raw):
    if not isinstance(raw,bytes) or not (1<=len(raw)<=MAX_VTT_BYTES):
        hold("caption file missing or oversized")
    text=raw.decode("utf-8-sig",errors="replace")
    if not text.lstrip().startswith("WEBVTT"):hold("caption payload not WebVTT")
    lines=[]; latest=-1.0; previous_start=-1.0; previous_end=-1.0; cues=0
    spoken=[]; cue_start=-1.0; cue_end=-1.0
    cue_lines=[]

    def remove_rolling_overlap(previous,incoming):
        # A later automatic caption may include repeated context from earlier
        # cues. Preserve only the new suffix; original VTT remains unmodified.
        length=min(len(previous),len(incoming),256)
        # One-word overlaps are too ambiguous: they may be intentional
        # repetitions rather than automatic-caption context.
        for size in range(length,1,-1):
            if previous[-size:]==incoming[:size]:
                return incoming[size:]
        return incoming

    def finish_cue():
        nonlocal cue_lines,previous_end,latest
        if not cue_lines:
            previous_end=max(previous_end,cue_end)
            return
        current=[]
        for line in cue_lines:
            clean=unescape(re.sub(r"<[^>]*>","",line)).strip()
            words=re.sub(r"\s+"," ",clean).split()
            if words:current.extend(remove_rolling_overlap(current,words))
        # Remove repeated rolling context only when cues overlap or are
        # nearly adjacent. Speech after a pause must NOT lose a repeated word.
        adjacent=(previous_end>=0 and cue_start<=previous_end+1.0)
        if current:
            # Empty/markup-only cues do not prove transcript coverage.
            latest=max(latest,cue_end)
        fresh=remove_rolling_overlap(spoken,current) if adjacent else current
        if fresh:
            spoken.extend(fresh)
            lines.append(" ".join(fresh))
        previous_end=max(previous_end,cue_end)
        cue_lines=[]

    rows=text.splitlines()
    active=False
    for index,line in enumerate(rows):
        m=TIME.match(line)
        if m:
            finish_cue()
            start=vtt_seconds(m.group("start"))
            endpoint=vtt_seconds(m.group("end"))
            if start<0 or endpoint<start or (previous_start>=0 and start<previous_start):
                hold("out-of-order or invalid caption cue timing")
            previous_start=start
            cue_start=start
            cue_end=endpoint
            # Coverage is committed by finish_cue() only after actual
            # readable caption text has been observed for this cue.
            cues+=1
            active=True
            continue
        # Named/numbered WebVTT cue IDs occur immediately BEFORE timing.
        if index+1<len(rows) and TIME.match(rows[index+1]):
            continue
        if not active or not line.strip() or line.startswith(("Kind:","Language:","NOTE")):
            continue
        cue_lines.append(line)
    finish_cue()
    if not lines or latest<=0:hold("no timestamped caption text")
    return ("\n".join(lines)+"\n").encode("utf-8"),{
        "source_cue_count":cues,
        "source_line_count":len(lines),
        "last_caption_second":round(latest,3)}

def captions_reach_end(last_caption_second,duration_seconds):
    if (not math.isfinite(last_caption_second) or
        not math.isfinite(duration_seconds) or duration_seconds<=0 or
        last_caption_second<=0):
        return False
    # A fixed 25-second grace period would swallow an entire short video.
    # End coverage does not prove continuous or semantic transcript coverage.
    tolerance=min(25.0,max(2.0,duration_seconds*0.02),duration_seconds*0.10)
    return abs(duration_seconds-last_caption_second)<=tolerance

def write_json(path,obj):
    path.write_text(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=True)+"\n")

def manifest_and_inventory(folder,url,receipt,tools):
    members=[]
    for name in MEMBERS:
        p=folder/name
        if not p.is_file() or p.is_symlink() or not p.stat().st_size:
            hold("missing canonical package member: "+name)
        members.append({"path":name,"sha256":file_sha(p),"bytes":p.stat().st_size})
    doc={"schema":"ghostmesh-reasoning-pack-v1","sourceUrl":url,
         "mediaPreparation":"direct-mp4-aac-remux-no-video-encode",
         "capture":{"source_mode":"public-no-browser-cookies",
                    "video_codec":receipt["video_codec"],
                    "audio_codec":receipt["audio_codec"],
                    "last_caption_second":receipt["last_caption_second"]},
         "tools":tools,"members":members}
    write_json(folder/"manifest.json",doc)
    with (folder/"SHA256SUMS.txt").open("w") as out:
        for name in (*MEMBERS,"manifest.json"):
            out.write(file_sha(folder/name)+"  "+name+"\n")
    return doc

def build(url,target,*,run=invoke,probe_media=probe,version_reader=None):
    vid=canonical_youtube(url)
    if target.exists() or target.is_symlink():hold("output already exists")
    if target.parent.is_symlink():hold("symlinked output parent")
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".reasonpack-fast-stage-",dir=target.parent))
    os.chmod(stage,0o700)
    try:
        metadata=stage/"source.json"
        with metadata.open("wb") as f:
            run(["yt-dlp","--ignore-config","--no-playlist","--skip-download",
                 "--dump-single-json",url],stdout=f)
        if metadata.stat().st_size>MAX_SOURCE_JSON:hold("source metadata too large")
        meta=json.loads(metadata.read_bytes())
        if (meta.get("id")!=vid or meta.get("is_live")
            or meta.get("live_status") in ("is_live","is_upcoming")):
            hold("source ID drift or live video unsupported")
        if isinstance(meta.get("duration"),bool):
            hold("source duration unavailable")
        try:
            source_duration=float(meta["duration"])
        except (ValueError,KeyError,TypeError,OverflowError):
            hold("source duration unavailable")
        if not math.isfinite(source_duration) or source_duration<=0:
            hold("invalid source duration")
        run(["yt-dlp","--ignore-config","--no-playlist",
             "-f","bv*[ext=mp4]+ba[ext=m4a]","--merge-output-format","mp4",
             "-o",str(stage/"video.%(ext)s"),url])
        video=stage/"video.mp4"
        if not video.is_file() or video.is_symlink() or not video.stat().st_size:
            hold("direct MP4 capture unavailable; no automatic re-encode")
        run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
             "-i",str(video),"-map","0:a:0","-vn","-c:a","copy",str(stage/"audio.m4a")])
        vp=probe_media(video); ap=probe_media(stage/"audio.m4a")
        media=validate_direct_media(video,stage/"audio.m4a",vp,ap)
        # Independent source-duration custody rejects outputs shortened
        # consistently across container, streams, audio and captions.
        source_tolerance=min(5.0,max(1.0,source_duration*0.01),
                             source_duration*0.05)
        if abs(media["duration_seconds"]-source_duration)>source_tolerance:
            hold("captured media duration differs from source metadata")
        write_json(stage/"ffprobe.json",vp)
        catalog=set((meta.get("subtitles") or {}).keys())
        catalog.update((meta.get("automatic_captions") or {}).keys())
        regional=sorted(x for x in catalog if re.fullmatch(r"en-[A-Za-z0-9-]+",x)
                        and x!="en-orig")
        languages=["en-orig","en",*regional]
        if catalog:
            languages=[x for x in languages if x in catalog]
        chosen=None
        transcript=None
        captions=None
        for language in languages:
            # One language at a time: failure of an unused translation cannot
            # invalidate an already available original English caption.
            try:
                run(["yt-dlp","--ignore-config","--no-playlist","--skip-download",
                     "--write-subs","--write-auto-subs",
                     "--sub-langs",language,"--sub-format","vtt",
                     "-o",str(stage/"captions.%(ext)s"),url])
            except subprocess.CalledProcessError:
                continue
            candidate=stage/("captions."+language+".vtt")
            if candidate.is_file() and not candidate.is_symlink():
                try:
                    text,coverage=timed_vtt(candidate.read_bytes())
                    if not captions_reach_end(coverage["last_caption_second"],
                                              media["duration_seconds"]):
                        continue
                except (ValueError,OSError,UnicodeError):
                    continue
                chosen=candidate
                transcript,captions=text,coverage
                break
        if chosen is None:hold("no usable full-length English captions; transcription required")
        os.replace(chosen,stage/"captions.vtt")
        for extra in stage.glob("captions.*.vtt"):
            if extra.exists():extra.unlink()
        (stage/"transcript.txt").write_bytes(transcript)
        write_json(stage/"transcript-status.json",
            {"status":"source-captions","sourceFile":"captions.vtt",
             "caption_line_count":captions["source_line_count"],
             "last_caption_second":captions["last_caption_second"]})
        versions=(version_reader or capture_tool_versions)()
        doc=manifest_and_inventory(stage,url,{**media,**captions},versions)
        repo_cli=ROOT/"bin/reasonpack"
        installed_cli=Path(__file__).resolve().parent/"reasonpack"
        verifier=repo_cli if repo_cli.is_file() else installed_cli
        if not verifier.is_file():hold("pinned canonical verifier not installed")
        run([str(verifier),"verify",str(stage)])
        if target.exists() or target.is_symlink():hold("output appeared during capture")
        os.replace(stage,target)
        return {"status":"canonical-direct-remux-verified",
                "video_id":vid,"pack":str(target),
                "manifest_sha256":file_sha(target/"manifest.json"),
                "media_mode":doc["mediaPreparation"],
                "video_codec":media["video_codec"],
                "duration_seconds":media["duration_seconds"],
                "transcript_lines":captions["source_line_count"],
                "video_reencoded":False,"model_invoked":False,"email_sent":False}
    finally:
        if stage.exists():shutil.rmtree(stage)

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source-url",required=True)
    cli.add_argument("--output",type=Path,required=True)
    args=cli.parse_args()
    try:
        print(json.dumps(build(args.source_url,args.output),sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired,UnicodeError,json.JSONDecodeError) as exc:
        print("HOLD: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
