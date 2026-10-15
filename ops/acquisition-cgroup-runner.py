#!/usr/bin/env python3
"""Systemd-cgroup containment launcher, SOURCE ONLY.

Only a qualified owner-installed instance named
ghostmesh-reasonpack-acquire@<64hex>.service may run real acquisition.
No ad hoc/root/uncontained fallback, no extra mail poller, no total video limit.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime,timezone

REPO=Path(__file__).resolve().parents[1]
JOBS=Path("/srv/ghostmesh/workspaces/runs/reasonpack-jobs")
ID=re.compile(r"^[a-f0-9]{64}$")
UNIT_PREFIX="ghostmesh-reasonpack-acquire@"
SCHEMA="ghostmesh.reasonpack.cgroup-runner-result.v1"

def refuse(msg):raise ValueError(msg)
def imported(name):
    spec=importlib.util.spec_from_file_location("rp_"+name.replace("-","_"),REPO/"ops"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def cgroup_path():
    lines=Path("/proc/self/cgroup").read_text().splitlines()
    records=[v.split("::",1)[1] for v in lines if v.startswith("0::")]
    if len(records)!=1:refuse("single unified cgroup v2 identity required")
    return records[0]

def verify_containment(job_id,cgroup=None):
    if not isinstance(job_id,str) or not ID.fullmatch(job_id):
        refuse("invalid immutable job identity")
    current=cgroup if cgroup is not None else cgroup_path()
    unit=UNIT_PREFIX+job_id+".service"
    if not isinstance(current,str) or not re.search(r"(?:^|/)"+re.escape(unit)+r"$",current):
        refuse("real acquisition must be inside exact approved systemd instance cgroup")
    if current.count("/"+unit)!=1:
        refuse("ambiguous unit/cgroup identity")
    return unit

def verify_install_contract(unit_text):
    """Parse exact unit policy from source. Does not install a service."""
    import configparser
    conf=configparser.ConfigParser(interpolation=None,strict=True)
    conf.optionxform=str
    conf.read_string(unit_text)
    svc=dict(conf["Service"])
    unit=dict(conf["Unit"])
    required={
       "Type":"exec","User":"ghostmesh","Group":"ghostmesh",
       "KillMode":"control-group","SendSIGKILL":"yes","Restart":"no",
       "NoNewPrivileges":"yes","PrivateTmp":"yes",
       "ProtectSystem":"strict","ProtectHome":"read-only",
       "TimeoutStartSec":"infinity","RuntimeMaxSec":"infinity",
       "MemoryMax":"8G","TasksMax":"128","CPUQuota":"200%",
       "UMask":"0077","OOMPolicy":"stop"
    }
    for key,value in required.items():
        if svc.get(key)!=value:refuse(f"missing protected systemd unit policy {key}")
    if ("ExecStart" not in svc or
        svc["ExecStart"]!="/usr/bin/python3 @IMMUTABLE_RELEASE_DIR@/ops/acquisition-cgroup-runner.py --job-id %i"
        or svc.get("WorkingDirectory")!="@IMMUTABLE_RELEASE_DIR@"):
        refuse("unit must require explicit reviewed immutable release rendering")
    if svc.get("ReadWritePaths")!=str(JOBS)+"/%i":
        refuse("write authority must be limited to the exact instance job directory")
    if not unit.get("Description","").startswith("GhostMesh ReasonPack"):
        refuse("unexpected systemd service purpose")
    if svc.get("ExecStartPre")!=(
        "+/usr/bin/python3 @IMMUTABLE_RELEASE_DIR@/ops/acquisition-owner-prestart.py --job-id %i"
    ) or "ExecStopPost" in svc:
        refuse("missing exact audited privileged one-time grant claim")
    if svc.get("ProtectControlGroups")!="yes" or svc.get("PrivateDevices")!="yes":
        refuse("missing cgroup or device protection")
    return {"unit_template":"ghostmesh-reasonpack-acquire@.service",
            "status":"source-policy-validated-not-installed",
            "cgroup_kill_policy":"control-group",
            "total_duration_limit":None,
            "network_acquisition_performed":False}

def verify_primary_runner(job_id,*,run=subprocess.run):
    """Only systemd's own MainPID may spend this unit's root-owned permit.

    A worker process in the same cgroup cannot become the original ExecStart
    PID and therefore cannot launch a second acquisition via a nested runner.
    """
    unit=verify_containment(job_id)
    try:
        result=run(["/usr/bin/systemctl","show",unit,"-p","MainPID","--value",
                    "--no-pager"],
                   stdin=subprocess.DEVNULL,capture_output=True,text=True,
                   timeout=6,env={"PATH":"/usr/bin:/bin","LC_ALL":"C"})
    except (OSError,subprocess.SubprocessError):
        refuse("systemd main PID readback unavailable")
    if result.returncode!=0 or not result.stdout.strip().isdigit():
        refuse("systemd main PID readback not authoritative")
    if int(result.stdout.strip())!=os.getpid() or os.getpid()<=1:
        refuse("only systemd registered primary runner may launch acquisition")
    return {"unit":unit,"main_pid":os.getpid(),"readback":"systemd-mainpid"}

def jobdir_for(job_id):
    verify_containment(job_id)
    root=JOBS
    if root.is_symlink() or not root.is_dir():refuse("dedicated root not provisioned")
    job=root/job_id
    if not job.is_dir() or job.is_symlink():refuse("immutable registered job unavailable")
    return job

def execute(job_id,*,guard=None,backend=None,child_runner=subprocess.Popen):
    """Foreground parent stays alive for entire worker lifetime.

    Systemd owns *this parent unit* and all subprocess descendants; the cgroup
    stops as one boundary even if worker or backend starts a new session.
    """
    verify_primary_runner(job_id)
    guard=guard or imported("acquisition-supervisor")
    backend=backend or imported("acquisition-real-worker")
    job=JOBS/job_id
    if job.is_symlink() or not job.is_dir():refuse("no registered job")
    # The preflight may read bytes but must never execute acquisition before
    # verifying the owner-signed grant from the trusted mail admission lane.
    fd=guard.lock(job)
    try:
        state=guard.state(job)
        if state.get("job_id")!=job_id or state.get("status")!="registered" or state.get("attempts")!=0:
            refuse("job not in unclaimed signed-admission state")
        raw_admission=(job/"admission.json").read_bytes()
        source=guard.validate_admission(raw_admission)
        if source["job_id"]!=job_id:refuse("job source mismatch")
        # A worker-writable job JSON/hash is NEVER permission to launch.
        # The only grant is signed by an external trusted Gmail intake signer,
        # bound to this immutable release + the exact registered intent.
        custody=imported("acquisition-signed-grant")
        approved=custody.verify_for_job(job,admission=raw_admission,
                               supervision=state,release_commit=REPO.name)
        # A root-only systemd ExecStartPre must have consumed this exact
        # grant first, in a durable ledger outside worker-writable storage.
        owner=imported("acquisition-owner-prestart")
        owner.verified_owner_permit(approved)
        backend.preflight()
        # A durable launch intent must precede logs and subprocess side effects.
        state.update(status="launch-intent-uncertain",worker_kind="real-acquisition",
                     attempts=1,work_started_at=datetime.now(timezone.utc).isoformat(),
                     worker_command_verified=False,
                     last_observation="systemd-contained launch claimed, work not yet verified")
        guard.atomic(job/"supervision.json",
                     (json.dumps(state,sort_keys=True,indent=2)+"\n").encode(),replace=True)
        worker=REPO/"ops/acquisition-real-worker.py"
        if worker.is_symlink() or not worker.is_file():refuse("fixed real worker missing")
        # Signed byte snapshot is passed on a sealed kernel memfd. Even if
        # the worker-writable admission file changes after verification, the
        # backend cannot consume a different video/source.
        handoff=imported("acquisition-sealed-admission")
        sealed_fd=handoff.seal_admission(raw_admission)
        try:
            rfd,wfd=os.pipe()
            proc=None
            try:
                with open(job/"contained-worker.stdout","xb",buffering=0) as out,open(
                     job/"contained-worker.stderr","xb",buffering=0) as err:
                    proc=child_runner([sys.executable,"-B",str(worker),
                            "--job",str(job),"--gate-fd",str(rfd),
                            "--admission-fd",str(sealed_fd)],
                         stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                         pass_fds=(rfd,sealed_fd),start_new_session=True,
                         env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8"})
                birth=guard.startticks(proc.pid)
                if not isinstance(birth,int):refuse("child PID/start identity unavailable")
                state.update(status="running",worker_pid=proc.pid,
                             worker_start_ticks=birth,worker_command_verified=True,
                             last_observation="contained source worker running, source unverified")
                guard.atomic(job/"supervision.json",
                             (json.dumps(state,sort_keys=True,indent=2)+"\n").encode(),replace=True)
                os.write(wfd,b"G")
            finally:
                os.close(rfd)
                os.close(wfd)
            rc=proc.wait()
        finally:
            os.close(sealed_fd)
        # The only positive outcome is an independent re-verification
        # of the complete pack. A worker's exit code alone proves nothing.
        result=guard.observe(job)
        if rc!=0 or not result.get("artifact_verified"):
            refuse("contained worker ended without independently verified source")
        if result.get("status") not in ("source-package-reverified",
                                     "completion-reported-process-still-running"):
            refuse("source observation not in verifiable terminal state")
        return {"schema":SCHEMA,"job_id":job_id,"source_manifest_sha256":result["verified_manifest_sha256"],
                "source_transcript_sha256":result["verified_transcript_sha256"],
                "containment_claim":"ran-inside-exact-systemd-service-cgroup",
                "systemd_instance":UNIT_PREFIX+job_id+".service",
                "independent_video_origin_attested":False,
                "send_authorized":False,"publication_authorized":False}
    finally:
        os.close(fd)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job-id",required=True)
    p.add_argument("--check-only",action="store_true")
    args=p.parse_args()
    try:
        identity=verify_containment(args.job_id)
        if args.check_only:
            print(json.dumps({"status":"cgroup-identity-verified","unit":identity,
                              "network_acquisition_started":False}))
        else:
            print(json.dumps(execute(args.job_id),sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError) as exc:
        print("HOLD: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
