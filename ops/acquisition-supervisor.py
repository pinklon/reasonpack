#!/usr/bin/env python3
"""Source-only durable ReasonPack acquisition supervisor.

Only runs a fixed bundled synthetic worker, never accepts an arbitrary command.
No overall job duration cutoff, no live queue/Slack/Gmail connection, and no
claim that a receipt submitted here independently proves email authentication.
A real acquisition backend requires a separately qualified adapter/release.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import fcntl
import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import shutil
import tempfile
from urllib.parse import urlsplit, parse_qs

ROOT=Path(__file__).resolve().parents[1]
SCHEMA="ghostmesh.reasonpack.acquisition-supervision.v1"
JOB_SCHEMA="ghostmesh.reasonpack.mail-job.v1"
SHA=re.compile(r"^[0-9a-f]{64}$")
VIDEO=re.compile(r"^[A-Za-z0-9_-]{11}$")

def fail(reason):raise ValueError(reason)
def hashraw(raw):return sha256(raw).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()

def atomic(path,raw,*,replace=False):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(prefix=".atomic-acq-",dir=path.parent)
    part=Path(name)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        if replace:os.replace(part,path)
        else:
            os.link(part,path)
        directory_fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
    finally:part.unlink(missing_ok=True)

def canonical_url(value):
    if not isinstance(value,str):fail("missing source URL")
    u=urlsplit(value)
    vid=parse_qs(u.query).get("v",[""])[0]
    if (u.scheme!="https" or u.hostname!="www.youtube.com" or u.path!="/watch"
        or u.username or u.password or u.port not in (None,443)
        or u.fragment or not VIDEO.fullmatch(vid) or value!="https://www.youtube.com/watch?v="+vid):
        fail("noncanonical admitted YouTube URL")
    return vid

def validate_admission(raw):
    if len(raw)>40_000:fail("oversized admission")
    a=json.loads(raw)
    if a.get("schema")!=JOB_SCHEMA or a.get("status")!="admitted-awaiting-acquisition":
        fail("acquisition requires prior admitted mail job")
    key=a.get("job_id")
    if not isinstance(key,str) or not SHA.fullmatch(key):fail("invalid job id")
    vid=canonical_url(a.get("source_url"))
    if vid!=a.get("video_id"):fail("video ID mismatch")
    if a.get("publication_authority") is not False or a.get("email_dispatch_authority") is not False:
        fail("admission cannot grant dispatch or publication")
    return a

def load(path):
    if path.is_symlink():fail("symlinked supervisor state")
    return json.loads(path.read_bytes())

def lock(jobdir):
    if not jobdir.is_dir() or jobdir.is_symlink():fail("invalid job directory")
    f=os.open(jobdir/".lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    fcntl.flock(f,fcntl.LOCK_EX)
    return f

def verified_gateway(receipt,envelope,allowed):
    from_env=os.environ.get("REASONPACK_MAIL_INGEST_KEY","")
    if len(from_env)<32:fail("gateway signing secret not commissioned")
    if not allowed:fail("explicit sender allowlist required")
    spec=importlib.util.spec_from_file_location("reasonpack_mail_authenticated",
                                             ROOT/"ops/mail-reasonpack.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bound=json.loads(envelope.read_bytes())
    sender,message_id,_,body=module.validate_envelope(
        bound,from_env.encode(),{x.strip().lower() for x in allowed})
    vid,url=module.parse_intent(body)
    source_id=bound.get("gmail_id") or message_id
    expected_id=hashraw((sender+"\0"+str(source_id)+"\0"+vid).encode())
    expected_fingerprint=hashraw(json.dumps(
        {k:v for k,v in bound.items() if k not in ("auth_tag","issued_at_utc")},
        sort_keys=True,separators=(",",":"),ensure_ascii=True).encode())
    if (receipt.get("sender")!=sender or receipt.get("message_id")!=message_id or
            receipt.get("job_id")!=expected_id or
            receipt.get("video_id")!=vid or receipt.get("source_url")!=url or
            receipt.get("admission_intent_sha256")!=expected_fingerprint or
            receipt.get("gmail_id")!=bound.get("gmail_id") or
            receipt.get("gmail_thread_id")!=bound.get("gmail_thread_id")):
        fail("receipt does not correspond to signed gateway identity and intent")
    return hashraw(envelope.read_bytes())

def register(receipt,root,envelope,allowed):
    raw=receipt.read_bytes()
    a=validate_admission(raw)
    signed_gateway_sha=verified_gateway(a,envelope,allowed)
    if root.is_symlink():fail("symlinked job root")
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=root/a["job_id"]
    if path.exists():
        if (path.is_symlink() or (path/"admission.json").read_bytes()!=raw or
            load(path/"supervision.json").get("signed_gateway_sha256")!=signed_gateway_sha):
            fail("same job identity has conflicting verified source")
        return {"status":"already-registered","job":str(path)}
    staging=Path(tempfile.mkdtemp(prefix=".register-acquisition-",dir=root))
    try:
        atomic(staging/"admission.json",raw)
        record={"schema":SCHEMA,"job_id":a["job_id"],"admission_sha256":hashraw(raw),
                "signed_gateway_sha256":signed_gateway_sha,
                "video_id":a["video_id"],"status":"registered",
                "worker_kind":"none","worker_pid":None,"worker_start_ticks":None,
                "worker_command_verified":False,"attempts":0,
                "work_started_at":None,"last_progress_at":None,
                "mission_elapsed_cutoff":None,
                "last_observation":"no worker has been started",
                "model_invoked":False,"email_dispatched":False,"public_release":False}
        atomic(staging/"supervision.json",(json.dumps(record,indent=2,sort_keys=True)+"\n").encode())
        if path.exists():fail("job appeared during registration; retry readback")
        os.rename(staging,path)
        root_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(root_fd)
        finally:os.close(root_fd)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return {"status":"registered","job":str(path)}

def state(path):
    a=validate_admission((path/"admission.json").read_bytes())
    s=load(path/"supervision.json")
    if s.get("schema")!=SCHEMA or s.get("job_id")!=a["job_id"] or s.get("admission_sha256")!=hashraw((path/"admission.json").read_bytes()):
        fail("supervision receipt identity drift")
    return s

def parse_proc_identity(raw):
    # /proc/[pid]/stat: field 3 is process state, field 22 is start ticks.
    # Zombie state retains PID/ticks despite having already exited.
    tail=raw.rsplit(")",1)[1].split()
    if tail[0] in {"Z","X","x"}:
        return None
    return int(tail[19])

def startticks(pid):
    if not isinstance(pid,int) or pid<=1:return None
    try:
        return parse_proc_identity(Path(f"/proc/{pid}/stat").read_text())
    except (ValueError,OSError,IndexError):return None

def live(s):
    pid=s.get("worker_pid")
    return bool(pid and isinstance(pid,int) and
                isinstance(s.get("worker_start_ticks"),int) and
                startticks(pid)==s["worker_start_ticks"])

def observe(jobdir):
    s=state(jobdir)
    heartbeat=jobdir/"heartbeat.json"
    if heartbeat.exists() and not heartbeat.is_symlink():
        h=load(heartbeat)
        if (h.get("schema")=="ghostmesh.reasonpack.synthetic-heartbeat.v1"
            and h.get("job_id")==s["job_id"] and h.get("worker_pid")==s["worker_pid"]
            and h.get("worker_start_ticks")==s["worker_start_ticks"] and
            h.get("sequence",0)>0):
            s["last_progress_at"]=h.get("observed_at_utc")
            s["last_progress_sequence"]=h["sequence"]
    terminal=jobdir/"synthetic-completion.json"
    completion=None
    if terminal.exists() and not terminal.is_symlink():
        value=load(terminal)
        if (value.get("schema")=="ghostmesh.reasonpack.synthetic-completion.v1"
            and value.get("job_id")==s["job_id"]
            and value.get("worker_pid")==s["worker_pid"]
            and value.get("worker_start_ticks")==s["worker_start_ticks"]
            and value.get("complete") is True):
            completion=value
    source_proof=None
    if s.get("worker_kind")=="real-acquisition":
        hb=jobdir/"real-acquisition-heartbeat.json"
        if hb.is_file() and not hb.is_symlink():
            report=load(hb)
            if (report.get("schema")=="ghostmesh.reasonpack.acquisition-real-heartbeat.v1"
                 and report.get("job_id")==s["job_id"]
                 and report.get("worker_pid")==s["worker_pid"]
                 and report.get("worker_start_ticks")==s["worker_start_ticks"]
                 and isinstance(report.get("sequence"),int) and report["sequence"]>0):
                s["last_progress_sequence"]=report["sequence"]
                s["last_progress_at"]=report.get("time_utc")
        result=jobdir/"real-acquisition-result.json"
        if result.is_file() and not result.is_symlink():
            item=load(result)
            if (item.get("schema")=="ghostmesh.reasonpack.acquisition-real-backend.v1"
                and item.get("status")=="WORKER_VERIFIED_SOURCE_PACKAGE"
                and item.get("job_id")==s["job_id"]
                and item.get("worker_pid")==s["worker_pid"]
                and item.get("worker_start_ticks")==s["worker_start_ticks"]
                and item.get("source_url")==validate_admission(
                    (jobdir/"admission.json").read_bytes())["source_url"]):
                spec=importlib.util.spec_from_file_location("real_backend_source_probe",
                                            ROOT/"ops/acquisition-real-worker.py")
                backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
                backend.preflight()
                check=backend.verify_source(jobdir,validate_admission(
                    (jobdir/"admission.json").read_bytes()))
                if (item.get("manifest_sha256")==check["manifest_sha256"]
                    and item.get("transcript_sha256")==check["transcript_sha256"]
                    and item.get("actual_backend_sha256")==backend.PIN):
                    source_proof=check
    running=live(s)
    if s["status"]=="registered":
        classification="registered-no-worker"
    elif s["status"]=="launch-intent-uncertain":
        classification="reconciliation-required-launch-uncertain"
    elif running and (completion or source_proof):
        classification="completion-reported-process-still-running"
    elif running and s.get("last_progress_sequence"):
        classification="running-worker-reported-progress"
    elif running:
        classification="running-progress-unknown"
    elif source_proof:
        classification="source-package-reverified"
    elif completion:
        classification="synthetic-fixture-complete"
    else:
        classification="reconciliation-required-no-auto-retry"
    return {"schema":SCHEMA,"job_id":s["job_id"],"status":classification,
            "worker_pid":s["worker_pid"],"worker_identity_matches":running,
            "last_progress_sequence":s.get("last_progress_sequence"),
            "last_progress_at":s.get("last_progress_at"),
            "progress_provenance":"worker-self-report-not-independent",
            "independent_progress_witness":False,
            "mission_elapsed_cutoff":None,
            "auto_retry_without_reconciliation":False,
            "automatic_restart_authorized":False,
            "provider_acceptance":"UNKNOWN",
            "actual_provider_billed_cost":None,
            "email_dispatched":False,
            "artifact_verified":bool(source_proof),
            "verified_manifest_sha256":source_proof["manifest_sha256"] if source_proof else None,
            "verified_transcript_sha256":source_proof["transcript_sha256"] if source_proof else None,
            "actual_provider_origin_attested":False,
            "synthetic_completion_reported":bool(completion),
            "independent_completion_attested":False,
            "production_acquisition_qualified":False}

def start_fixture(jobdir,ticks,period_ms):
    if not 1<=ticks<=100 or not 1<=period_ms<=1000:fail("invalid bounded fixture parameters")
    fd=lock(jobdir)
    try:
        s=state(jobdir)
        if s["status"]!="registered" or s["attempts"]!=0:fail("fixture already launched or state not registered")
        child=ROOT/"ops/acquisition-synthetic-worker.py"
        if not child.is_file():fail("fixed synthetic worker missing")
        # Durable intent BEFORE log-file or subprocess side effects. Even if
        # the launcher dies on Popen, the next observer sees an uncertain
        # attempt and cannot quietly dispatch duplicate work.
        s.update(status="launch-intent-uncertain",worker_kind="synthetic-only",
                 worker_command_verified=False,attempts=1,
                 work_started_at=utc(),
                 last_observation="launch claimed; PID/start identity not yet durably established")
        atomic(jobdir/"supervision.json",
               (json.dumps(s,indent=2,sort_keys=True)+"\n").encode(),replace=True)
        readfd,writefd=os.pipe()
        out=open(jobdir/"fixture.stdout","xb",buffering=0)
        err=open(jobdir/"fixture.stderr","xb",buffering=0)
        try:
            proc=subprocess.Popen([
                 sys.executable,"-B",str(child),
                 "--job",str(jobdir),"--ticks",str(ticks),
                 "--period-ms",str(period_ms),"--gate-fd",str(readfd)
              ],stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                 pass_fds=(readfd,),start_new_session=True,
                 env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8"})
        finally:
            os.close(readfd);out.close();err.close()
        try:
            birth=startticks(proc.pid)
            if not isinstance(birth,int):fail("cannot attest fixture PID/start identity")
            s.update(status="running",worker_kind="synthetic-only",
                     worker_pid=proc.pid,worker_start_ticks=birth,
                     worker_command_verified=True,attempts=1,work_started_at=utc(),
                     last_observation="fixture subprocess launched, waiting for gated start")
            atomic(jobdir/"supervision.json",
                   (json.dumps(s,indent=2,sort_keys=True)+"\n").encode(),replace=True)
            # Only now allow the subprocess to begin writing progress.
            os.write(writefd,b"G")
        finally:
            os.close(writefd)
        return {"status":"synthetic-worker-started","pid":proc.pid,
                "job_id":s["job_id"],"mission_elapsed_cutoff":None,
                "real_acquisition_started":False}
    finally:os.close(fd)

def start_real(jobdir,expected_cli_sha,permit_network):
    """Manual, explicit source-only adapter. Never used by legacy intake."""
    if permit_network is not True:
        fail("real network acquisition requires explicit operator authorization")
    spec=importlib.util.spec_from_file_location("reasonpack_real_backend",
                                               ROOT/"ops/acquisition-real-worker.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if expected_cli_sha!=module.PIN:
        fail("operator-approved CLI digest does not match reviewed source pin")
    module.preflight()
    fd=lock(jobdir)
    try:
        s=state(jobdir)
        if s["status"]!="registered" or s["attempts"]!=0:
            fail("source worker was already claimed or is uncertain")
        admitted=validate_admission((jobdir/"admission.json").read_bytes())
        worker=ROOT/"ops/acquisition-real-worker.py"
        if worker.is_symlink() or not worker.is_file():
            fail("fixed real worker implementation missing")
        s.update(status="launch-intent-uncertain",worker_kind="real-acquisition",
                 attempts=1,worker_command_verified=False,
                 work_started_at=utc(),
                 last_observation="real acquisition explicitly claimed, worker result unknown")
        atomic(jobdir/"supervision.json",
               (json.dumps(s,indent=2,sort_keys=True)+"\n").encode(),replace=True)
        readfd,writefd=os.pipe()
        proc=None
        try:
            with open(jobdir/"real-worker.stdout","xb",buffering=0) as out,open(
                    jobdir/"real-worker.stderr","xb",buffering=0) as err:
                proc=subprocess.Popen([sys.executable,"-B",str(worker),
                                       "--job",str(jobdir),"--gate-fd",str(readfd)],
                             stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                             pass_fds=(readfd,),start_new_session=True,
                             env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8"})
            birth=startticks(proc.pid)
            if not isinstance(birth,int):fail("real worker PID/start identity unavailable")
            s.update(status="running",worker_pid=proc.pid,
                     worker_start_ticks=birth,worker_command_verified=True,
                     last_observation="real worker started, acquisition still unverified")
            atomic(jobdir/"supervision.json",
                   (json.dumps(s,indent=2,sort_keys=True)+"\n").encode(),replace=True)
            os.write(writefd,b"G")
        finally:
            os.close(readfd)
            os.close(writefd)
        return {"status":"source-worker-started-unverified",
                "pid":proc.pid,"job_id":admitted["job_id"],
                "mission_elapsed_cutoff":None,
                "email_dispatched":False,"public_release":False}
    finally:
        os.close(fd)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="cmd",required=True)
    register_cmd=sub.add_parser("register")
    register_cmd.add_argument("--admission",type=Path,required=True)
    register_cmd.add_argument("--root",type=Path,required=True)
    register_cmd.add_argument("--envelope",type=Path,required=True)
    register_cmd.add_argument("--allow-sender",action="append",required=True)
    for verb in ("launch-fixture","launch-real","status"):
        s=sub.add_parser(verb);s.add_argument("--job",type=Path,required=True)
        if verb=="launch-fixture":
            s.add_argument("--ticks",type=int,default=5)
            s.add_argument("--period-ms",type=int,default=100)
        if verb=="launch-real":
            s.add_argument("--permit-network-acquisition",action="store_true")
            s.add_argument("--expected-cli-sha256",required=True)
    a=p.parse_args()
    try:
        if a.cmd=="register":result=register(a.admission,a.root,a.envelope,a.allow_sender)
        elif a.cmd=="launch-fixture":result=start_fixture(a.job,a.ticks,a.period_ms)
        elif a.cmd=="launch-real":
            result=start_real(a.job,a.expected_cli_sha256,a.permit_network_acquisition)
        else:result=observe(a.job)
        print(json.dumps(result,sort_keys=True));return 0
    except (ValueError,TypeError,KeyError,FileNotFoundError,OSError,
            json.JSONDecodeError,subprocess.SubprocessError) as exc:
        print("HOLD: "+str(exc),file=sys.stderr);return 2

if __name__=="__main__":raise SystemExit(main())
