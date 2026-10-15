#!/usr/bin/env python3
"""Pinned ReasonPack acquisition backend, invokable only by durable supervisor.

No Gmail/Slack sending, publishing, billing or model access. Real-network work
requires a separate operator invocation; this module is never on a live timer.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time

REPO=Path(__file__).resolve().parents[1]
CLI=Path("/home/ghostmesh/.local/share/reasonpack/reasonpack")
PIN="3fb0e0b7b4eb0977671b12de9b28d9a41fa6f539a2b0ba6e426f6643238b6fef"
SCHEMA="ghostmesh.reasonpack.acquisition-real-backend.v1"

def deny(s):raise ValueError(s)
def digest(path):
    h=sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def identity(pid):
    try:
        t=Path(f"/proc/{pid}/stat").read_text().rsplit(")",1)[1].split()
        return int(t[19]) if t[0] not in ("Z","X","x") else None
    except (OSError,ValueError,IndexError):return None

def safe_group(pid):
    try:return os.getpgid(pid)
    except ProcessLookupError:return None

def atomic(path,obj):
    fd,name=tempfile.mkstemp(prefix=".verified-backend-",dir=path.parent)
    staging=Path(name)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w") as f:
            json.dump(obj,f,sort_keys=True)
            f.write("\n");f.flush();os.fsync(f.fileno())
        os.replace(staging,path)
        d=os.open(path.parent,os.O_DIRECTORY|os.O_RDONLY)
        try:os.fsync(d)
        finally:os.close(d)
    finally:staging.unlink(missing_ok=True)

def preflight(cli=CLI,pin=PIN):
    if cli.is_symlink() or not cli.is_file():deny("fixed ReasonPack implementation unavailable")
    observed=digest(cli)
    if observed!=pin:deny("installed acquisition CLI drift; source must be reviewed")
    return {"backend":str(cli),"sha256":observed,
            "command_mode":"reasonpack build CANONICAL_URL DEDICATED_EMPTY_DIR",
            "network_acquisition_performed":False}

def isolated_env(job):
    home=job/"isolated-home"
    if home.is_symlink():deny("HOME cannot be a symlink")
    home.mkdir(mode=0o700,exist_ok=True)
    xdg=home/".config"
    if xdg.is_symlink():deny("config root cannot be a symlink")
    xdg.mkdir(mode=0o700,exist_ok=True)
    return {"PATH":"/home/ghostmesh/.local/bin:/usr/bin:/bin",
            "HOME":str(home),"XDG_CONFIG_HOME":str(xdg),
            "LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}

def verify_source(job,receipt,verifier=CLI,run=subprocess.run):
    output=job/"raw-acquisition"
    if not output.is_dir() or output.is_symlink():deny("source pack missing")
    verified=run([str(verifier),"verify",str(output)],
                 capture_output=True,text=True,timeout=90,
                 env=isolated_env(job))
    if verified.returncode:deny("ReasonPack pack verifier rejected acquired evidence")
    manifest=json.loads((output/"manifest.json").read_text("utf-8"))
    source=json.loads((output/"source.json").read_text("utf-8"))
    if (manifest.get("schema")!="ghostmesh-reasoning-pack-v1"
        or manifest.get("sourceUrl")!=receipt["source_url"]
        or source.get("id")!=receipt["video_id"]):
        deny("source manifest/video identity mismatch")
    for name in ("video.mp4","audio.m4a","transcript.txt"):
        f=output/name
        if f.is_symlink() or not f.is_file() or f.stat().st_size==0:
            deny("required source artifact missing")
    return {"manifest_sha256":digest(output/"manifest.json"),
        "transcript_sha256":digest(output/"transcript.txt"),
        "source_id":source["id"],
        "video_bytes":(output/"video.mp4").stat().st_size,
        "audio_bytes":(output/"audio.m4a").stat().st_size}

def output_hint(output):
    if not output.is_dir():return "no-source-output-yet"
    # File presence is observable, not corroboration or guaranteed progress.
    for name,description in (("manifest.json","unverified-manifest-present"),
                             ("transcript.txt","unverified-transcript-present"),
                             ("video.mp4","unverified-normalized-video-present"),
                             ("source.json","unverified-provider-metadata-present")):
        if (output/name).exists():return description
    return "source-processing-state-unknown"

def observed_file_sizes(directory):
    """Best-effort source progress; transient file removal cannot fail a job."""
    try:
        count=0
        size=0
        for path in directory.iterdir():
            try: info=path.lstat()
            except (FileNotFoundError,NotADirectoryError,PermissionError):
                continue
            if stat.S_ISREG(info.st_mode):
                size+=info.st_size
                count+=1
        return {"bytes":size,"files":count,"scan_complete":True}
    except OSError:
        return {"bytes":None,"files":None,"scan_complete":False}

def execute(job,receipt,*,cli=CLI,pin=PIN,runner=subprocess.Popen,verify_runner=subprocess.run,
            interval=0.5,max_log_bytes=8_000_000):
    preflight(cli,pin)
    output=job/"raw-acquisition"
    if output.exists() or output.is_symlink():deny("source output already exists: inspect before retry")
    output.mkdir(mode=0o700)
    env=isolated_env(job)
    stdout=job/"real-acquisition.stdout"
    stderr=job/"real-acquisition.stderr"
    child=None
    success=False
    with stdout.open("xb",buffering=0) as out,stderr.open("xb",buffering=0) as err:
        try:
            child=runner([str(cli),"build",receipt["source_url"],str(output)],
                         stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                         start_new_session=True,env=env)
            sequence=0
            while True:
                sequence+=1
                rc=child.poll()
                hints=observed_file_sizes(output)
                atomic(job/"real-acquisition-heartbeat.json",{
                    "schema":"ghostmesh.reasonpack.acquisition-real-heartbeat.v1",
                    "job_id":receipt["job_id"],"worker_pid":os.getpid(),
                    "worker_start_ticks":identity(os.getpid()),
                    "backend_pid":child.pid,
                    "backend_start_ticks":identity(child.pid),
                    "backend_pgid":safe_group(child.pid) if rc is None else None,
                    "sequence":sequence,
                    "time_utc":datetime.now(timezone.utc).isoformat(),
                    "phase_hint":output_hint(output),
                    "observed_source_bytes":hints["bytes"],
                    "observed_source_files":hints["files"],
                    "progress_scan_complete":hints["scan_complete"],
                    "actual_source_integrity":"NOT_VERIFIED_UNTIL_COMPLETION",
                    "source_report_authority":"WORKER_SELF_REPORT",
                    "mission_duration_limit":None,"email_dispatched":False})
                if stdout.stat().st_size+stderr.stat().st_size>max_log_bytes:
                    deny("bounded log-resource ceiling exceeded, reconciliation required")
                if rc is not None:
                    if rc:deny("fixed acquisition backend exited without verified source")
                    break
                time.sleep(interval)
            # Recheck the exact backend bytes after execution before
            # attaching the approved binary digest to the result receipt.
            preflight(cli,pin)
            source=verify_source(job,receipt,verifier=cli,run=verify_runner)
            record={"schema":SCHEMA,"job_id":receipt["job_id"],
                    "worker_pid":os.getpid(),"worker_start_ticks":identity(os.getpid()),
                    "status":"WORKER_VERIFIED_SOURCE_PACKAGE",
                    "source_url":receipt["source_url"],"video_id":receipt["video_id"],
                    **source,"actual_backend_sha256":pin,
                    "independent_public_origin_attested":False,
                    "verified_media_claims":False,"model_invoked":False,
                    "email_dispatched":False,"public_release":False,
                    "provider_billed_amount":"UNKNOWN"}
            atomic(job/"real-acquisition-result.json",record)
            success=True
            return record
        finally:
            if child is not None and not success and child.poll() is None:
                try:os.killpg(child.pid,signal.SIGTERM)
                except ProcessLookupError:pass

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job",type=Path,required=True)
    ap.add_argument("--gate-fd",type=int,required=True)
    args=ap.parse_args()
    try:
        if os.read(args.gate_fd,1)!=b"G":deny("no authorized parent release")
        os.close(args.gate_fd)
        spec=importlib.util.spec_from_file_location("acquisition_source_guard",
                                                    REPO/"ops/acquisition-supervisor.py")
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        if args.job.is_symlink() or not args.job.is_dir():deny("invalid job root")
        source=mod.validate_admission((args.job/"admission.json").read_bytes())
        state=mod.state(args.job)
        if (state["status"]!="running" or state["worker_kind"]!="real-acquisition"
            or state["worker_pid"]!=os.getpid() or
            state["worker_start_ticks"]!=identity(os.getpid())):
            deny("worker did not match supervisor launch commitment")
        execute(args.job,source)
        return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        print("SOURCE HOLD:",str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
