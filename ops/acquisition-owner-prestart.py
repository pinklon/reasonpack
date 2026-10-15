#!/usr/bin/env python3
"""Owner-only, one-attempt ReasonPack launch claim for systemd ExecStartPre.

Source-only: no installed privileged helper, issuer, private key, or live job.
The systemd template must invoke this exact source as root with a fixed job ID.
Never launch an actual worker from here.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys

REPO=Path(__file__).resolve().parents[1]
LEDGER_ROOT=Path("/var/lib/ghostmesh/reasonpack")
DB=LEDGER_ROOT/"launch-claims.sqlite3"
PERMITS=LEDGER_ROOT/"permits"
JOBS=Path("/srv/ghostmesh/workspaces/runs/reasonpack-jobs")
HEX64=re.compile(r"^[a-f0-9]{64}$")
HEX40=re.compile(r"^[a-f0-9]{40}$")
SCHEMA="ghostmesh.reasonpack.owner-launch-claim.v1"
TABLE_DDL="""CREATE TABLE launch_claims (
job_id TEXT NOT NULL PRIMARY KEY,
nonce TEXT NOT NULL UNIQUE,
grant_sha256 TEXT NOT NULL UNIQUE,
release_commit TEXT NOT NULL,
admission_sha256 TEXT NOT NULL,
gateway_sha256 TEXT NOT NULL,
claimed_at_utc TEXT NOT NULL
)"""

def refuse(message):raise ValueError(message)

def imp(filename):
    p=REPO/"ops"/(filename+".py")
    spec=importlib.util.spec_from_file_location("rp_claim_"+filename.replace("-","_"),p)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def require_owner():
    if os.geteuid()!=0:refuse("root-only launch claim authority required")

def check_part(path,*,isfile=False):
    try:info=path.lstat()
    except OSError:refuse("root-owned launch ledger unavailable: "+str(path))
    expected=stat.S_ISREG if isfile else stat.S_ISDIR
    if (not expected(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022):
        refuse("unsafe or writable owner ledger path: "+str(path))
    if isfile and info.st_mode & 0o077:
        refuse("launch ledger must be root-private")
    return info

def check_ledger_custody(*,db=DB,permits=PERMITS):
    if db!=DB or permits!=PERMITS:
        refuse("unapproved owner ledger path")
    for p in (Path("/var"),Path("/var/lib"),Path("/var/lib/ghostmesh"),LEDGER_ROOT,PERMITS):
        check_part(p)
    check_part(DB,isfile=True)
    if DB.stat().st_size==0:refuse("uninitialized owner launch ledger")
    return True

def claim_record(authorized):
    fields=("job_id","nonce","grant_sha256","release_commit",
            "source_admission_sha256","signed_gateway_sha256")
    for name in fields:
        value=authorized.get(name)
        size=40 if name=="release_commit" else 64
        pat=HEX40 if size==40 else HEX64
        if not isinstance(value,str) or not pat.fullmatch(value):
            refuse("owner claim lacks exact signed field: "+name)
    if authorized.get("launch_authorized") is not True:
        refuse("cryptographic owner grant not independently verified")
    return {
      "schema":SCHEMA,"job_id":authorized["job_id"],"nonce":authorized["nonce"],
      "grant_sha256":authorized["grant_sha256"],
      "release_commit":authorized["release_commit"],
      "admission_sha256":authorized["source_admission_sha256"],
      "gateway_sha256":authorized["signed_gateway_sha256"],
      "claim_role":"one-time-prestart-authority",
      "claimed_at_utc":datetime.now(timezone.utc).isoformat()
    }

def claim_once(authorized,*,db,permitdir):
    """Perform one durable claim, no retries after uncertain commit.

    Caller must have authenticated the signed original grant and must own
    custody of the protected SQLite database/permit directory.
    """
    record=claim_record(authorized)
    target=permitdir/(record["job_id"]+".json")
    if target.is_symlink() or target.exists():
        refuse("owner permit already exists: replay or incomplete prior attempt")
    with sqlite3.connect(db,timeout=8,isolation_level=None) as con:
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA busy_timeout=8000")
        con.execute("BEGIN IMMEDIATE")
        try:
            # Fail closed if an owner-issued job, nonce, or grant digest has
            # ever been claimed by any earlier release or worker attempt.
            con.execute("""INSERT INTO launch_claims
              (job_id,nonce,grant_sha256,release_commit,admission_sha256,
               gateway_sha256,claimed_at_utc) VALUES (?,?,?,?,?,?,?)""",
              (record["job_id"],record["nonce"],record["grant_sha256"],
               record["release_commit"],record["admission_sha256"],
               record["gateway_sha256"],record["claimed_at_utc"]))
            payload=(json.dumps(record,sort_keys=True,separators=(",",":"))+"\n").encode()
            fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,"wb") as f:
                os.fchmod(f.fileno(),0o644)
                f.write(payload);f.flush();os.fsync(f.fileno())
            dirfd=os.open(permitdir,os.O_DIRECTORY|os.O_RDONLY)
            try:os.fsync(dirfd)
            finally:os.close(dirfd)
            con.execute("COMMIT")
        except (sqlite3.DatabaseError,OSError):
            con.execute("ROLLBACK")
            # A permit possibly left behind on IO/DB errors deliberately
            # blocks automatic retries; owner reconciliation is required.
            raise
    return record

def check_permit_bytes(authorized,raw):
    """Validate one protected owner-produced permit against signed bytes."""
    expected=claim_record(authorized)
    if not isinstance(raw,bytes) or not (24<=len(raw)<=2048):
        refuse("owner permit missing or oversized")
    try:observed=json.loads(raw)
    except (ValueError,UnicodeError):refuse("owner permit is not valid JSON")
    if not isinstance(observed,dict) or set(observed)!=set(expected):
        refuse("owner permit schema/fields do not match reviewed policy")
    for field in ("schema","job_id","nonce","grant_sha256","release_commit",
                  "admission_sha256","gateway_sha256","claim_role"):
        if observed.get(field)!=expected[field]:
            refuse("owner permit does not match exact signed acquisition grant")
    if not isinstance(observed.get("claimed_at_utc"),str):
        refuse("owner claim time not recorded")
    return True

def verified_owner_permit(authorized,*,permits=PERMITS):
    """Unprivileged runner reads a root-owned permit; never modifies ledger."""
    record=claim_record(authorized)
    target=permits/(record["job_id"]+".json")
    for p in (Path("/var"),Path("/var/lib"),Path("/var/lib/ghostmesh"),
              LEDGER_ROOT,permits):
        check_part(p)
    try:info=target.lstat()
    except OSError:refuse("owner one-time claim permit unavailable")
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
        refuse("owner permit is symlinked or writable by worker")
    if info.st_size>2048 or info.st_size==0:refuse("invalid owner permit length")
    return check_permit_bytes(authorized,target.read_bytes())

def initialize_ledger():
    """Explicit owner administrative initialization, never called on start."""
    require_owner()
    if LEDGER_ROOT.exists() or LEDGER_ROOT.is_symlink():
        refuse("owner ledger initialization is create-only")
    for p in (Path("/var"),Path("/var/lib"),Path("/var/lib/ghostmesh")):
        check_part(p)
    os.mkdir(LEDGER_ROOT,0o755)
    os.mkdir(PERMITS,0o755)
    # Force traversal for the non-root worker to read ONLY the public
    # permit; the private SQLite ledger remains root-only 0600.
    os.chmod(LEDGER_ROOT,0o755)
    os.chmod(PERMITS,0o755)
    fd=os.open(DB,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600)
    os.close(fd)
    with sqlite3.connect(DB) as con:
        con.execute(TABLE_DDL)
    os.chmod(DB,0o600)
    check_ledger_custody()
    return {"status":"initialized-owner-ledger-not-a-grant",
            "private_key_created":False,"worker_started":False}

def prestart(job_id):
    require_owner()
    if not isinstance(job_id,str) or not HEX64.fullmatch(job_id):
        refuse("invalid systemd job instance")
    if REPO.parent!=Path("/opt/ghostmesh/reasonpack/releases"):
        refuse("prestart must execute exact root-owned immutable release")
    release_commit=REPO.name
    if not HEX40.fullmatch(release_commit):refuse("unreviewed immutable release")
    check_ledger_custody()
    guard=imp("acquisition-supervisor")
    signed=imp("acquisition-signed-grant")
    safe=imp("acquisition-safe-owner-io")
    # Pin the exact job directory and open only bounded regular members via
    # O_NOFOLLOW, O_NONBLOCK, dir_fd and fstat. Root must never perform the
    # worker's prior pathname-based verification routines.
    with safe.opened_job(job_id) as jobfd:
        admission=safe.read_regular_member(jobfd,"admission.json",40_000)
        raw_state=safe.read_regular_member(jobfd,"supervision.json",65_536)
        raw_grant=safe.read_regular_member(jobfd,"launch-grant.json",8_192)
        signature=safe.read_regular_member(jobfd,"launch-grant.sig",4_096)
        source=guard.validate_admission(admission)
        state=json.loads(raw_state)
        if not isinstance(state,dict):
            refuse("signed job state not an object")
        if (source.get("job_id")!=job_id or state.get("schema")!=guard.SCHEMA
            or state.get("job_id")!=job_id
            or state.get("admission_sha256")!=guard.hashraw(admission)
            or state.get("status")!="registered" or state.get("attempts")!=0):
            refuse("job already attempted or unbound registered state")
        record=signed.verify_from_bytes(raw_grant,signature,admission,
                                        state,release_commit)
        result=claim_once(record,db=DB,permitdir=PERMITS)
    return {"job_id":job_id,"grant_sha256":result["grant_sha256"],
        "owner_claim_consumed":True,"worker_started":False,
        "network_acquisition_performed":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--job-id")
    group.add_argument("--init-owner-ledger",action="store_true")
    args=p.parse_args()
    try:
        result=initialize_ledger() if args.init_owner_ledger else prestart(args.job_id)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,sqlite3.DatabaseError,TypeError) as e:
        print("OWNER HOLD: "+str(e),file=sys.stderr)
        return 2
if __name__=="__main__":raise SystemExit(main())
