#!/usr/bin/env python3
"""Segment a verified ReasonPack transcript without limiting video duration.

Each segment has a bounded size; the number of segments is unbounded. Neither
source bytes nor canonical ReasonPack members are modified. Segment boundaries
are UTF-8-safe, contiguous, and SHA-256-verifiable. No models/network/sends.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

SCHEMA="ghostmesh.reasonpack.segments.v1"
DEFAULT_TARGET=20_000
MIN_TARGET=512
MAX_TARGET=48_000
TIME=re.compile(r"\b(?:(\d{1,3}):)?(\d{1,2}):(\d{2})\b")

def refuse(why):raise ValueError(why)
def digest(b):return sha256(b).hexdigest()

def streamhash(path):
    h=sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(256*1024),b""):h.update(b)
    return h.hexdigest()

def emit_segments(transcript,directory,target):
    if not MIN_TARGET<=target<=MAX_TARGET:refuse("invalid per-segment byte budget")
    directory.mkdir()
    names=[]
    offset=0
    chunk=bytearray()
    totalhash=sha256()
    def emit():
        nonlocal offset,chunk
        if not chunk:return
        raw=bytes(chunk)
        try: txt=raw.decode("utf-8")
        except UnicodeDecodeError:refuse("transcript segmentation broke UTF-8")
        number=len(names)
        name=f"segment-{number:06d}.txt"
        path=directory/name
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as fp:fp.write(raw);fp.flush();os.fsync(fp.fileno())
        matches=TIME.findall(txt)
        names.append({"index":number,"path":name,"start_byte":offset,
                      "end_byte":offset+len(raw),"bytes":len(raw),"sha256":digest(raw),
                      "timestamp_tokens":len(matches)})
        offset+=len(raw)
        chunk=bytearray()
    def append(piece):
        nonlocal chunk
        while piece:
            room=target-len(chunk)
            if len(piece)<=room:
                chunk.extend(piece);return
            if room==0:emit();continue
            # Prefer complete newline boundaries. If a single source line exceeds
            # the segment budget, split at a UTF-8 code point boundary.
            cut=room
            while cut>0 and cut<len(piece) and (piece[cut]&0xC0)==0x80:
                cut-=1
            if cut==0:
                emit()
                continue
            chunk.extend(piece[:cut])
            piece=piece[cut:]
            emit()
    # Fixed-size text reads avoid unbounded readline() on a single giant
    # subtitle line and ensure each encoded piece begins/ends at UTF-8
    # codepoint boundaries. Repeated byte slicing is bounded by 4096 * 4
    # bytes rather than the total transcript size.
    with transcript.open("r",encoding="utf-8",newline="") as fp:
        while text:=fp.read(4096):
            piece=text.encode("utf-8")
            totalhash.update(piece)
            append(piece)
    emit()
    if not names:refuse("empty transcript")
    return names,offset,totalhash.hexdigest()

def build(pack,out,target,repo):
    if out.exists() or out.is_symlink():refuse("segment destination exists")
    if not pack.is_dir() or pack.is_symlink():refuse("pack path invalid")
    v=subprocess.run([str(repo/"bin/reasonpack"),"verify",str(pack)],
                     capture_output=True,text=True,timeout=90)
    if v.returncode:refuse("canonical source verifier rejected pack")
    raw_manifest=(pack/"manifest.json").read_bytes()
    canonical=json.loads(raw_manifest)
    if canonical.get("schema")!="ghostmesh-reasoning-pack-v1":
        refuse("unexpected source manifest")
    t=pack/"transcript.txt"
    if t.is_symlink() or not t.is_file():
        refuse("canonical transcript cannot be a symlink")
    expected=[m for m in canonical["members"] if m.get("path")=="transcript.txt"]
    if len(expected)!=1 or expected[0].get("sha256")!=streamhash(t):
        refuse("source transcript hash mismatch")
    out.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(dir=out.parent,prefix=".longform-"))
    try:
        # Directory contains only numbered segments and manifest.
        parts,bytecount,sha=emit_segments(t,staging/"segments",target)
        if bytecount!=t.stat().st_size or sha!=expected[0]["sha256"]:
            refuse("segmented source custody mismatch")
        record={"schema":SCHEMA,"source_manifest_sha256":digest(raw_manifest),
                "transcript_sha256":sha,"transcript_bytes":bytecount,
                "target_chunk_bytes":target,"segment_count":len(parts),
                "segments":parts,"video_duration_limit":None,
                "method":"streaming-UTF8-bytes-no-duration-cutoff",
                "model_invoked":False,"public_release":False}
        (staging/"segments-manifest.json").write_text(json.dumps(record,indent=2)+"\n")
        verify(t,staging)
        if out.exists():refuse("segment destination appeared during build")
        os.rename(staging,out)
        return {"result":"segments-verified","count":len(parts),
                "transcript_sha256":sha,"output":str(out)}
    finally:
        if staging.exists():shutil.rmtree(staging)

def verify(transcript,out):
    manpath=out/"segments-manifest.json"
    data=json.loads(manpath.read_text())
    if data.get("schema")!=SCHEMA:refuse("wrong segment schema")
    members=data.get("segments")
    if not isinstance(members,list) or not members or len(members)!=data.get("segment_count"):
        refuse("wrong segment census")
    folder=out/"segments"
    if not folder.is_dir() or folder.is_symlink():refuse("missing segments directory")
    expected_names={f"segment-{i:06d}.txt" for i in range(len(members))}
    if {p.name for p in folder.iterdir()}!=expected_names:refuse("extra or missing segments")
    if {p.name for p in out.iterdir()}!={"segments","segments-manifest.json"}:
        refuse("unexpected segment output members")
    h=sha256();expected_offset=0
    with transcript.open("rb") as original:
        for i,entry in enumerate(members):
            if not isinstance(entry,dict) or entry.get("index")!=i or entry.get("path")!=f"segment-{i:06d}.txt":
                refuse("wrong segment ordering")
            f=folder/entry["path"]
            if f.is_symlink() or not f.is_file():refuse("symlink or missing segment")
            length=entry.get("bytes")
            if not isinstance(length,int) or not 0<length<=MAX_TARGET:
                refuse("invalid segment length")
            if entry.get("start_byte")!=expected_offset or entry.get("end_byte")!=expected_offset+length:
                refuse("noncontiguous byte offsets")
            raw=f.read_bytes()
            if len(raw)!=length or digest(raw)!=entry.get("sha256"):
                refuse("segment checksum mismatch")
            try:raw.decode("utf-8")
            except UnicodeDecodeError:refuse("invalid UTF-8 chunk")
            if original.read(length)!=raw:refuse("segment diverges from canonical transcript")
            h.update(raw);expected_offset+=length
        if original.read(1):refuse("uncovered source transcript suffix")
    if expected_offset!=data.get("transcript_bytes") or h.hexdigest()!=data.get("transcript_sha256"):
        refuse("full transcript was not reconstructed exactly")
    if transcript.stat().st_size!=expected_offset:
        refuse("transcript changed during verification")
    return data

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    a=sub.add_parser("build");a.add_argument("--pack",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    a.add_argument("--target-bytes",type=int,default=DEFAULT_TARGET)
    v=sub.add_parser("verify");v.add_argument("--transcript",type=Path,required=True)
    v.add_argument("--segments",type=Path,required=True)
    args=p.parse_args()
    try:
        if args.mode=="build":
            result=build(args.pack,args.out,args.target_bytes,Path(__file__).resolve().parents[1])
        else:
            manifest=verify(args.transcript,args.segments)
            result={"result":"segments-verified","count":manifest["segment_count"],
                    "transcript_sha256":manifest["transcript_sha256"]}
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print("HOLD: "+str(exc),file=sys.stderr);return 2

if __name__=="__main__":raise SystemExit(main())
