#!/usr/bin/env python3
"""Fixed non-network acquisition supervisor fixture. Never used for real video."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

def ticks(pid):
    raw=Path(f"/proc/{pid}/stat").read_text()
    return int(raw.rsplit(")",1)[1].split()[19])

def write(path,item):
    fd,name=tempfile.mkstemp(prefix=".fixture-stage-",dir=path.parent)
    tmp=Path(name)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w") as f:
            json.dump(item,f,sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--job",type=Path,required=True)
    ap.add_argument("--ticks",type=int,required=True)
    ap.add_argument("--period-ms",type=int,required=True)
    ap.add_argument("--gate-fd",type=int,required=True)
    a=ap.parse_args()
    if not 1<=a.ticks<=100 or not 1<=a.period_ms<=1000:return 2
    gate=os.read(a.gate_fd,1)
    os.close(a.gate_fd)
    if gate!=b"G":return 3
    admission=json.loads((a.job/"admission.json").read_text())
    s=json.loads((a.job/"supervision.json").read_text())
    pid=os.getpid()
    if (s.get("worker_kind")!="synthetic-only" or
        s.get("worker_pid")!=pid or s.get("worker_start_ticks")!=ticks(pid)):
        return 4
    for seq in range(1,a.ticks+1):
        time.sleep(a.period_ms/1000.0)
        write(a.job/"heartbeat.json",{
            "schema":"ghostmesh.reasonpack.synthetic-heartbeat.v1",
            "job_id":s["job_id"],"worker_pid":pid,
            "worker_start_ticks":s["worker_start_ticks"],
            "sequence":seq,"observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "progress_kind":"synthetic-only-no-provider"})
    write(a.job/"synthetic-completion.json",{
        "schema":"ghostmesh.reasonpack.synthetic-completion.v1",
        "job_id":s["job_id"],"worker_pid":pid,
        "worker_start_ticks":s["worker_start_ticks"],
        "complete":True,"completed_at_utc":datetime.now(timezone.utc).isoformat(),
        "artifact_created":False,"provider_acceptance":"NOT_APPLICABLE"})
    return 0
if __name__=="__main__":
    raise SystemExit(main())
