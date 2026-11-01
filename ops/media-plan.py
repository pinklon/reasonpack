#!/usr/bin/env python3
"""Choose stream-copy or encode from inspected source codecs, fail closed."""
import json
import subprocess
import sys

def modes(probe):
    streams=probe.get("streams")
    if not isinstance(streams,list):
        raise ValueError("ffprobe stream inventory missing")
    video=next((s for s in streams if s.get("codec_type")=="video"),None)
    audio=next((s for s in streams if s.get("codec_type")=="audio"),None)
    if video is None or audio is None:
        raise ValueError("ReasonPack requires both video and audio")
    v="copy" if video.get("codec_name")=="h264" and video.get("pix_fmt")=="yuv420p" else "encode"
    a="copy" if audio.get("codec_name")=="aac" else "encode"
    return v,a

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: media-plan.py SOURCE")
    p=subprocess.run(["ffprobe","-v","error","-show_streams","-of","json",sys.argv[1]],
                     capture_output=True,text=True,timeout=45)
    if p.returncode:
        raise SystemExit("source media probe failed")
    try:
        v,a=modes(json.loads(p.stdout))
    except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        raise SystemExit(f"source media not qualified: {exc}")
    print(v,a)

if __name__=="__main__":main()
