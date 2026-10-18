#!/usr/bin/env python3
"""Import a verified Mac ReasonPack/1.0 as a provenance-preserving VPS source pack.

Never labels an imported pack as freshly downloaded or independently attested.
The original artifact members, SHA inventory, and originating manifest remain
available as immutable members of the derived canonical pack.
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
from urllib.parse import urlsplit, parse_qs

ORIGINAL={"video.mp4","audio.m4a","transcript.srt","transcript.txt",
          "manifest.json","SHA256SUMS.txt","REASONING.md"}
VID=re.compile(r"^[A-Za-z0-9_-]{11}$")
SCHEMA="ghostmesh-reasoning-pack-v1"

def reject(message):
    raise ValueError(message)

def digest(p):
    h=sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def verify_original(src:Path):
    if not src.is_dir() or src.is_symlink():
        reject("original source must be a real directory")
    entries={p.name for p in src.iterdir()}
    if entries != ORIGINAL or any((src/name).is_symlink() or not (src/name).is_file() for name in ORIGINAL):
        reject("Mac source directory has missing, untracked or linked members")
    original={}
    checksum_raw=(src/"SHA256SUMS.txt").read_bytes()
    for line in checksum_raw.decode("utf-8").splitlines():
        parts=line.split("  ",1)
        if len(parts)!=2:
            reject("malformed original SHA inventory")
        hash_value,name=parts
        if name not in ORIGINAL-{"SHA256SUMS.txt"} or name in original or not re.fullmatch(r"[0-9a-f]{64}",hash_value):
            reject("unexpected or repeated SHA inventory member")
        original[name]=hash_value
    if set(original)!=ORIGINAL-{"SHA256SUMS.txt"}:
        reject("incomplete Mac source SHA inventory")
    for name,hash_value in original.items():
        if digest(src/name)!=hash_value:
            reject("original source byte integrity failure: "+name)
    manifest_raw=(src/"manifest.json").read_bytes()
    if sha256(manifest_raw).hexdigest()!=original["manifest.json"]:
        reject("original manifest changed after SHA verification")
    manifest=json.loads(manifest_raw)
    if manifest.get("schema")!="reasonpack/1.0" or not isinstance(manifest.get("source"),dict):
        reject("invalid originating ReasonPack manifest")
    source=manifest["source"]
    vid=source.get("video_id")
    if not isinstance(vid,str) or not VID.fullmatch(vid):
        reject("invalid source video identity")
    url="https://www.youtube.com/watch?v="+vid
    if source.get("url")!=url or source.get("type")!="youtube":
        reject("source URL and video identity mismatch")
    if manifest.get("transcript",{}).get("status")!="captions":
        reject("only source-caption Mac packs currently supported")
    catalog={}
    files=manifest.get("files")
    if not isinstance(files,list):
        reject("invalid source file inventory")
    for row in files:
        if not isinstance(row,dict):
            reject("invalid original member")
        name=row.get("name")
        if name in catalog or name not in {"video.mp4","audio.m4a","transcript.srt","transcript.txt"}:
            reject("unexpected original manifest member")
        if row.get("sha256")!=original[name] or row.get("bytes")!=(src/name).stat().st_size:
            reject("source manifest disagrees with verified original bytes")
        catalog[name]=row
    if set(catalog)!={"video.mp4","audio.m4a","transcript.srt","transcript.txt"}:
        reject("incomplete original file catalog")
    original["SHA256SUMS.txt"]=sha256(checksum_raw).hexdigest()
    return manifest,url,original

def import_pack(src,out,refkit):
    manifest,url,original=verify_original(src)
    source_root=src.resolve()
    target=out.resolve()
    if source_root==target or source_root in target.parents:
        reject("target must be outside the verified source pack")
    if out.exists() or out.is_symlink():
        reject("target already exists; no overwrites")
    if not refkit.is_file():
        reject("canonical ReasonPack verifier unavailable")
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".mac-pack-import-",dir=out.parent))
    try:
        for name in ("video.mp4","audio.m4a","transcript.srt","transcript.txt","REASONING.md"):
            shutil.copyfile(src/name,stage/name)
        shutil.copyfile(src/"manifest.json",stage/"origin-manifest.json")
        shutil.copyfile(src/"SHA256SUMS.txt",stage/"origin-SHA256SUMS.txt")
        original_targets={
            "video.mp4":"video.mp4", "audio.m4a":"audio.m4a",
            "transcript.srt":"transcript.srt", "transcript.txt":"transcript.txt",
            "REASONING.md":"REASONING.md", "manifest.json":"origin-manifest.json",
            "SHA256SUMS.txt":"origin-SHA256SUMS.txt",
        }
        for original_name,staged_name in original_targets.items():
            if digest(stage/staged_name)!=original[original_name]:
                reject("verified original source changed while staging: "+original_name)
        evidence={"status":"source-captions","sourceFile":"transcript.srt",
                  "caption_origin":"original Mac ReasonPack/1.0 source-caption export",
                  "original_source_manifest_sha256":original["manifest.json"],
                  "original_caption_sha256":original["transcript.srt"],
                  "caption_accuracy_verified":False}
        (stage/"transcript-status.json").write_text(json.dumps(evidence,indent=2)+"\n")
        source={"id":manifest["source"]["video_id"],"title":manifest["source"].get("title"),
                "channel":manifest["source"].get("channel"),
                "webpage_url":url,
                "importType":"verified-mac-reasonpack-1.0",
                "original_manifest_sha256":original["manifest.json"],
                "fresh_youtube_download":False}
        (stage/"source.json").write_text(json.dumps(source,indent=2)+"\n")
        proc=subprocess.run(["ffprobe","-v","error","-show_format","-show_streams","-of","json",
                             str(stage/"video.mp4")],capture_output=True,timeout=45)
        if proc.returncode or not proc.stdout:
            reject("normalized video failed technical probe")
        (stage/"ffprobe.json").write_bytes(proc.stdout)
        files=sorted(p.name for p in stage.iterdir() if p.is_file())
        produced={"schema":SCHEMA,"sourceUrl":url,"tools":{"importer":"verified-mac-pack-v1",
                    "ffprobe":"locally measured"},
                  "importedFrom":{"schema":"reasonpack/1.0",
                    "sourceManifestSha256":original["manifest.json"],
                    "originalShasumSha256":original["SHA256SUMS.txt"],
                    "freshProviderRetrieval":False},
                  "members":[{"path":name,"sha256":digest(stage/name),
                              "bytes":(stage/name).stat().st_size} for name in files]}
        (stage/"manifest.json").write_text(json.dumps(produced,indent=2)+"\n")
        checksum_lines=[digest(stage/name)+"  "+name for name in files+["manifest.json"]]
        (stage/"SHA256SUMS.txt").write_text("\n".join(checksum_lines)+"\n")
        verification=subprocess.run([str(refkit),"verify",str(stage)],
                                    capture_output=True,text=True,timeout=45)
        if verification.returncode:
            reject("canonical output rejected by verifier: "+verification.stderr[-250:])
        original_targets={
            "video.mp4":"video.mp4", "audio.m4a":"audio.m4a",
            "transcript.srt":"transcript.srt", "transcript.txt":"transcript.txt",
            "REASONING.md":"REASONING.md", "manifest.json":"origin-manifest.json",
            "SHA256SUMS.txt":"origin-SHA256SUMS.txt",
        }
        for original_name,staged_name in original_targets.items():
            if digest(stage/staged_name)!=original[original_name]:
                reject("verified original source changed while staging: "+original_name)
        os.rename(stage,out)
        print(json.dumps({"status":"verified-import-not-fresh-download",
                          "source":url,"canonical_pack":str(out),
                          "canonical_manifest_sha256":digest(out/"manifest.json"),
                          "original_manifest_sha256":original["manifest.json"],
                          "source_video_sha256":digest(out/"video.mp4"),
                          "source_transcript_sha256":digest(out/"transcript.txt")},sort_keys=True))
    finally:
        if stage.exists():
            shutil.rmtree(stage)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verifier",type=Path,default=Path(__file__).resolve().parents[1]/"bin/reasonpack")
    args=parser.parse_args()
    try:
        import_pack(args.source,args.out,args.verifier)
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError,subprocess.TimeoutExpired) as e:
        print("HOLD: "+str(e),file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
