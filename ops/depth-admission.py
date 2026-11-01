#!/usr/bin/env python3
"""Local-only immutable editorial-depth admission; no mail, model or worker authority."""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

SCHEMA="ghostmesh.reasonpack.offline-depth-admission.v1"
HERE=Path(__file__).resolve().parent

def refuse(message):
    raise ValueError(message)

def resolve(depth):
    spec=importlib.util.spec_from_file_location("depth_profile",HERE/"depth-profile.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resolve(depth)["name"]

def load(job):
    if job.is_symlink() or not job.is_dir():
        refuse("offline job directory unavailable or symlinked")
    path=job/"depth-admission.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size>4096:
        refuse("offline depth admission missing or invalid")
    raw=path.read_bytes()
    record=json.loads(raw)
    if (set(record)!={"schema","depth_profile","source_manifest_sha256"}
            or record["schema"]!=SCHEMA
            or not isinstance(record["source_manifest_sha256"],str)
            or not re.fullmatch("[0-9a-f]{64}",record["source_manifest_sha256"])):
        refuse("invalid offline depth admission")
    resolve(record["depth_profile"])
    return record,sha256(raw).hexdigest()

def init(job,manifest,depth):
    resolved=resolve(depth)
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>1000000:
        refuse("invalid source manifest path")
    source_sha=sha256(manifest.read_bytes()).hexdigest()
    record={"schema":SCHEMA,"depth_profile":resolved,"source_manifest_sha256":source_sha}
    if job.exists() or job.is_symlink():
        existing,_=load(job)
        if existing!=record:
            refuse("offline job ID reused with changed source or depth")
        return {"status":"duplicate-identical","depth_profile":resolved}
    job.parent.mkdir(parents=True,exist_ok=True)
    os.mkdir(job,0o700)
    path=job/"depth-admission.json"
    raw=(json.dumps(record,sort_keys=True)+"\n").encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as file:
        file.write(raw)
    return {"status":"created","depth_profile":resolved}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("init","check"))
    p.add_argument("--job",required=True,type=Path)
    p.add_argument("--manifest",type=Path)
    p.add_argument("--depth",choices=("short","standard","deep","exhaustive"))
    args=p.parse_args()
    try:
        if args.command=="init":
            if not args.manifest:refuse("init requires --manifest")
            result=init(args.job,args.manifest,args.depth or "standard")
        else:
            record,admission_sha=load(args.job)
            if args.depth and args.depth!=record["depth_profile"]:
                refuse("offline job depth differs from admitted profile")
            result={"status":"verified","depth_profile":record["depth_profile"],
                    "admission_sha256":admission_sha,
                    "source_manifest_sha256":record["source_manifest_sha256"]}
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,FileNotFoundError,json.JSONDecodeError,OSError) as error:
        print("HOLD: "+str(error),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
