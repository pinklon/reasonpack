#!/usr/bin/env python3
"""Render an owner-reviewable, immutable ReasonPack systemd release candidate.

DRY RUN ONLY: does not create a real release directory, install a systemd unit,
start a worker, touch /root, change a symlink, send email or download media.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import shutil

ROOT=Path(__file__).resolve().parents[1]
SCHEMA="ghostmesh.reasonpack.owner-install-preflight.v1"
SHA40=re.compile(r"^[a-f0-9]{40}$")
SHA64=re.compile(r"^[a-f0-9]{64}$")
RELEASE_ROOT=Path("/srv/ghostmesh/workspaces/runtime/reasonpack/releases")
SOURCE_TEMPLATE=ROOT/"ops/systemd/ghostmesh-reasonpack-acquire@.service"
WORKER=ROOT/"ops/acquisition-real-worker.py"
CLI=ROOT/"bin/reasonpack"

def deny(message):raise ValueError(message)
def sha(data):return sha256(data).hexdigest()

def release_path(commit):
    if not isinstance(commit,str) or not SHA40.fullmatch(commit):
        deny("exact 40-hex reviewed source commit required")
    return RELEASE_ROOT/commit

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def review_sources():
    for f in (SOURCE_TEMPLATE,WORKER,CLI):
        if f.is_symlink() or not f.is_file():deny("release source file unavailable or symlinked")
    worker=module(WORKER,"reasonpack_pinned_worker_release_candidate")
    if worker.CLI!=CLI:
        deny("real acquisition backend is not pinned to same release CLI")
    if worker.PIN!=sha(CLI.read_bytes()):
        deny("immutable release CLI SHA does not match reviewed worker pin")
    guard=module(ROOT/"ops/acquisition-cgroup-runner.py","reasonpack_cgroup_release_policy")
    template=SOURCE_TEMPLATE.read_text("utf-8")
    if "@IMMUTABLE_RELEASE_DIR@" not in template:
        deny("systemd template does not require immutable release substitution")
    guard.verify_install_contract(template)
    if "launch-real" in (ROOT/"ops/acquisition-supervisor.py").read_text():
        deny("unmanaged direct real acquisition launcher still present")
    return template

def render(commit):
    template=review_sources()
    target=release_path(commit)
    text=template.replace("@IMMUTABLE_RELEASE_DIR@",str(target))
    if "@IMMUTABLE_RELEASE_DIR@" in text or "/current/" in text:
        deny("unrendered or mutable release path in unit")
    expected="ExecStart=/usr/bin/python3 "+str(target)+"/ops/acquisition-cgroup-runner.py --job-id %i"
    if expected not in text or "WorkingDirectory="+str(target) not in text:
        deny("release service executable not bound to exact source revision")
    if text.count(str(target))!=2:
        deny("unexpected substitution scope in service")
    return text

def git_revision():
    r=subprocess.run(["git","-C",str(ROOT),"rev-parse","--verify","HEAD"],
                     capture_output=True,text=True,timeout=8)
    if r.returncode:deny("missing pinned Git checkout identity")
    revision=r.stdout.strip()
    if not SHA40.fullmatch(revision):deny("malformed commit hash")
    s=subprocess.run(["git","-C",str(ROOT),"status","--porcelain=v1","--untracked-files=all"],
                     capture_output=True,text=True,timeout=8)
    if s.returncode or s.stdout.strip():deny("release source is dirty; commit and requalify before proposal")
    return revision

def build(commit,out):
    source=git_revision()
    if source!=commit:deny("checked-out source is not exact owner-reviewed commit")
    if out.exists() or out.is_symlink():deny("preflight output already exists")
    text=render(commit)
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".reasonpack-release-preflight-",dir=out.parent))
    try:
        unit=stage/"ghostmesh-reasonpack-acquire@.service"
        unit.write_text(text)
        os.chmod(unit,0o600)
        record={
            "schema":SCHEMA,"source_commit":commit,
            "source_tree":str(ROOT),"candidate_release_path":str(release_path(commit)),
            "source_cli_sha256":sha(CLI.read_bytes()),
            "source_worker_sha256":sha(WORKER.read_bytes()),
            "source_runner_sha256":sha((ROOT/"ops/acquisition-cgroup-runner.py").read_bytes()),
            "rendered_unit_sha256":sha(text.encode()),
            "requested_change":"owner-review immutable acquisition cgroup instance template",
            "installer_executed":False,"systemd_unit_installed":False,
            "unit_enabled":False,"worker_started":False,"network_requested":False,
            "owner_authorization_bound_to_hash":False,
            "cgroup_kill_witness":"NOT_ATTESTED",
            "rollback_witness":"NOT_ATTESTED",
            "canary_email":"NOT_ATTEMPTED",
            "public_release":False
        }
        payload=(json.dumps(record,indent=2,sort_keys=True)+"\n").encode()
        receipt=stage/"preflight-receipt.json"
        receipt.write_bytes(payload)
        os.chmod(receipt,0o600)
        if sha(unit.read_bytes())!=record["rendered_unit_sha256"]:
            deny("rendered unit drift before atomic publication")
        os.rename(stage,out)
        return {"status":"source-only-proposal","source_commit":commit,
                "candidate_release_path":str(release_path(commit)),
                "unit_sha256":record["rendered_unit_sha256"],
                "installer_executed":False}
    finally:
        if stage.exists():shutil.rmtree(stage)

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--exact-commit",required=True)
    a.add_argument("--out",type=Path,required=True)
    args=a.parse_args()
    try:
        print(json.dumps(build(args.exact_commit,args.out),sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired) as e:
        print("HOLD: "+str(e),file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
