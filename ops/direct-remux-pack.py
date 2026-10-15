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
TIME=re.compile(r"^(\d\d):(\d\d):(\d\d)\.(\d{3}) -->")
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
    if vd<=0 or ad<=0 or abs(vd-ad)>max(5,vd*0.01):
        hold("video/audio durations disagree")
    if any(not p.is_file() or p.is_symlink() or p.stat().st_size==0 for p in (video,audio)):
        hold("invalid direct media member")
    return {"video_codec":vc[0],"audio_codec":"aac","duration_seconds":vd}

def timed_vtt(raw):
    if not isinstance(raw,bytes) or not (1<=len(raw)<=MAX_VTT_BYTES):
        hold("caption file missing or oversized")
    text=raw.decode("utf-8-sig",errors="replace")
    if not text.lstrip().startswith("WEBVTT"):hold("caption payload not WebVTT")
    last=None; lines=[]; latest=-1.0; cues=0
    for line in text.splitlines():
        m=TIME.match(line)
        if m:
            h,minute,sec,milli=(int(x) for x in m.groups())
            latest=h*3600+minute*60+sec+milli/1000
            cues+=1
            continue
        if latest<0 or not line.strip() or line.startswith(("Kind:","Language:","NOTE")):
            continue
        normalized=unescape(re.sub(r"<[^>]*>","",line)).strip()
        normalized=re.sub(r"\s+"," ",normalized)
        if normalized and normalized!=last:
            lines.append(normalized);last=normalized
    if not lines or latest<=0:hold("no timestamped caption text")
    return ("\n".join(lines)+"\n").encode("utf-8"),{
        "source_cue_count":cues,
        "source_line_count":len(lines),
        "last_caption_second":round(latest,3)}

def write_json(path,obj):
    path.write_text(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=True)+"\n")

def manifest_and_inventory(folder,url,receipt):
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
         "tools":{},"members":members}
    write_json(folder/"manifest.json",doc)
    with (folder/"SHA256SUMS.txt").open("w") as out:
        for name in (*MEMBERS,"manifest.json"):
            out.write(file_sha(folder/name)+"  "+name+"\n")
    return doc

def build(url,target,*,run=invoke,probe_media=probe):
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
        write_json(stage/"ffprobe.json",vp)
        run(["yt-dlp","--ignore-config","--no-playlist","--skip-download",
             "--write-subs","--write-auto-subs",
             "--sub-langs","en-orig,en","--sub-format","vtt",
             "-o",str(stage/"captions.%(ext)s"),url])
        options=[stage/name for name in ("captions.en-orig.vtt","captions.en.vtt")
                 if (stage/name).is_file()]
        if not options:hold("no English captions; transcription required")
        chosen=options[0]
        os.replace(chosen,stage/"captions.vtt")
        for extra in options[1:]:
            if extra.exists():extra.unlink()
        transcript,captions=timed_vtt((stage/"captions.vtt").read_bytes())
        (stage/"transcript.txt").write_bytes(transcript)
        if captions["last_caption_second"]<media["duration_seconds"]-max(25,media["duration_seconds"]*0.02):
            hold("source caption coverage incomplete")
        write_json(stage/"transcript-status.json",
            {"status":"source-captions","sourceFile":"captions.vtt",
             "caption_line_count":captions["source_line_count"],
             "last_caption_second":captions["last_caption_second"]})
        doc=manifest_and_inventory(stage,url,{**media,**captions})
        run([str(ROOT/"bin/reasonpack"),"verify",str(stage)])
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
