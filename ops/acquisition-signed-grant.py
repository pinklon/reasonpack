#!/usr/bin/env python3
"""Read-only acquisition grant verification. No key generation or signer included.

A struct-valid JSON admission is NOT sufficient authority to run a downloader.
This module verifies a detached OpenSSH Ed25519 signature from a separate,
owner-controlled Gmail-admission signer; only a public key enters the worker.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess

SCHEMA="ghostmesh.reasonpack.acquisition-owner-grant.v1"
PRINCIPAL="ghostmesh-reasonpack-admission"
NAMESPACE="ghostmesh.reasonpack.acquisition.v1"
TRUST=Path("/etc/ghostmesh/reasonpack/approved_signers")
SHA64=re.compile(r"[0-9a-f]{64}\Z")
SHA40=re.compile(r"[0-9a-f]{40}\Z")
MAX_BYTES=8192
MAX_SIGNATURE_BYTES=4096

def reject(msg):raise ValueError(msg)
def hashbytes(raw):return sha256(raw).hexdigest()

def parse_timestamp(value):
    if not isinstance(value,str) or len(value)>40:
        reject("invalid grant timestamp")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:reject("invalid grant timestamp")
    if t.tzinfo is None:reject("grant timestamp must carry UTC offset")
    return t.astimezone(timezone.utc)

def validate_payload(raw,*,admission_raw,supervision,release_commit,now=None):
    """Strict, canonical single-job payload binding. No signature proof here."""
    if not isinstance(raw,bytes) or not (5<len(raw)<=MAX_BYTES):
        reject("grant size rejected")
    if not isinstance(admission_raw,bytes) or len(admission_raw)>40_000:
        reject("admission input not bounded")
    if not SHA40.fullmatch(release_commit):
        reject("installed immutable release identity absent")
    try:g=json.loads(raw)
    except (ValueError,UnicodeError):reject("malformed grant payload")
    keys={"schema","job_id","source_url","video_id","admission_sha256",
          "signed_gateway_sha256","release_commit","scope","nonce",
          "issued_at_utc","expires_at_utc"}
    if not isinstance(g,dict) or set(g)!=keys:
        reject("grant fields or schema drift")
    canonical=(json.dumps(g,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode()
    if raw!=canonical:reject("noncanonical signed grant bytes")
    if g["schema"]!=SCHEMA or g["scope"]!="owner-only-real-acquisition":
        reject("grant scope is not a reviewed acquisition request")
    if not SHA64.fullmatch(g["job_id"]) or not SHA64.fullmatch(g["nonce"]):
        reject("invalid grant job or nonce identity")
    if not SHA64.fullmatch(g["admission_sha256"]) or not SHA64.fullmatch(g["signed_gateway_sha256"]):
        reject("malformed signed source hashes")
    if g["release_commit"]!=release_commit:
        reject("grant does not authorize this immutable release")
    try: a=json.loads(admission_raw)
    except (ValueError,UnicodeError):reject("malformed source admission")
    if (g["job_id"]!=a.get("job_id") or
        g["source_url"]!=a.get("source_url") or
        g["video_id"]!=a.get("video_id") or
        g["admission_sha256"]!=hashbytes(admission_raw) or
        supervision.get("job_id")!=g["job_id"] or
        supervision.get("admission_sha256")!=g["admission_sha256"] or
        supervision.get("signed_gateway_sha256")!=g["signed_gateway_sha256"]):
        reject("grant does not bind the registered authenticated Gmail intent")
    issued=parse_timestamp(g["issued_at_utc"])
    expires=parse_timestamp(g["expires_at_utc"])
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:reject("verification clock must be timezone aware")
    now=now.astimezone(timezone.utc)
    if not (now-timedelta(hours=24)<=issued<=now+timedelta(minutes=5)):
        reject("grant issue time outside allowed window")
    if not (issued<expires<=issued+timedelta(hours=24) and expires>=now):
        reject("grant expired or validity period invalid")
    # Expiration is checked ONLY at launch; it never imposes a total media/video runtime.
    return {"job_id":g["job_id"],"grant_sha256":hashbytes(raw),
            "source_admission_sha256":g["admission_sha256"],
            "signed_gateway_sha256":g["signed_gateway_sha256"],
            "release_commit":release_commit,"nonce":g["nonce"],
            "scope":g["scope"],"expires_at_utc":g["expires_at_utc"],
            "launch_authorized":False}

def verify_file_signature(raw,signature,signers):
    # The signature is produced by the external, privileged Gmail authority.
    # Verification needs only the public signer, not the private signing key.
    import tempfile
    fd,name=tempfile.mkstemp(prefix="reasonpack-verify-signature-",suffix=".sig")
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as f:f.write(signature)
        p=subprocess.run(["/usr/bin/ssh-keygen","-Y","verify",
            "-f",str(signers),"-I",PRINCIPAL,"-n",NAMESPACE,"-s",name],
            input=raw,capture_output=True,timeout=12)
        if p.returncode!=0:reject("owner admission grant signature invalid")
        return True
    finally:Path(name).unlink(missing_ok=True)

def check_root_public_signer_custody(path=TRUST):
    if path!=TRUST:reject("unapproved public signer registry path")
    for segment in (Path("/etc"),Path("/etc/ghostmesh"),
                    Path("/etc/ghostmesh/reasonpack"),TRUST):
        try:info=segment.lstat()
        except OSError:reject("owner-controlled public signer registry not commissioned")
        mode=info.st_mode
        expected_type=stat.S_ISREG if segment==TRUST else stat.S_ISDIR
        if not expected_type(mode) or info.st_uid!=0 or mode & 0o022:
            reject("public signer registry lacks root-controlled custody")
    if TRUST.stat().st_size>16384 or TRUST.stat().st_size==0:
        reject("public signer registry missing or oversized")
    # No wildcards, arbitrary principals, certificate authorities or
    # alternative algorithms are admitted by this initial single-signer lane.
    lines=TRUST.read_text("utf-8").splitlines()
    if len(lines)!=1:
        reject("one exact owner public signer required until rotation is reviewed")
    parts=lines[0].split()
    if (len(parts)!=3 or parts[0]!=PRINCIPAL or parts[1]!="ssh-ed25519"
        or not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}",parts[2])):
        reject("owner signer identity or public algorithm not explicitly pinned")
    return True

def verify_for_job(job,admission,supervision,release_commit):
    """Fail-closed real worker entrypoint; never creates or reads private keys."""
    if job.is_symlink() or not job.is_dir():
        reject("unsafe real acquisition job root")
    check_root_public_signer_custody()
    path=job/"launch-grant.json"
    sig=job/"launch-grant.sig"
    if any(p.is_symlink() or not p.is_file() for p in (path,sig)):
        reject("signed owner launch grant not commissioned")
    if path.stat().st_size>MAX_BYTES or sig.stat().st_size>MAX_SIGNATURE_BYTES:
        reject("signed owner grant oversized")
    raw=path.read_bytes()
    signature=sig.read_bytes()
    record=validate_payload(raw,admission_raw=admission,
        supervision=supervision,release_commit=release_commit)
    verify_file_signature(raw,signature,TRUST)
    record["launch_authorized"]=True
    record["signature_method"]="openssh-ed25519-external-owner-signer"
    return record
