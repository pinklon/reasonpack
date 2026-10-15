#!/usr/bin/env python3
"""Immutable, local-only GhostMesh ReasonPack Reader job orchestrator.

No Gmail calls, external publication, model invocation, credential handling or
service mutation. Jobs progress through explicit evidence-backed transitions.
"""
from __future__ import annotations

import argparse
import fcntl
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ghostmesh.reasonpack.workflow.v1"
STATES = ("admitted", "source-verified", "awaiting-research",
          "research-evidence-verified", "analysis-unreviewed",
          "reader-private-draft", "email-private-draft")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
VIDEO = re.compile(r"^[A-Za-z0-9_-]{11}$")

def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def reject(message: str):
    raise ValueError(message)

def data(path: Path):
    return json.loads(path.read_text("utf-8"))

def protect_write(path: Path, raw: bytes):
    if path.exists() or path.is_symlink():
        reject("immutable artifact already exists")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())

def checkpoint(jobdir: Path, payload: dict):
    tmp = jobdir / ".workflow.tmp"
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    if tmp.exists():
        reject("interrupted state transaction requires inspection")
    protect_write(tmp, raw)
    os.replace(tmp, jobdir / "workflow.json")

def lock_job(jobdir: Path):
    if not jobdir.is_dir() or jobdir.is_symlink():
        reject("expected real job directory")
    fd = os.open(jobdir / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd

def state(jobdir: Path, expected: str | None = None):
    flow = data(jobdir / "workflow.json")
    if flow.get("schema") != SCHEMA or flow.get("state") not in STATES:
        reject("corrupt workflow state")
    if expected and flow["state"] != expected:
        reject(f"invalid workflow transition, expected {expected}, got {flow['state']}")
    admission = (jobdir / "admission.json").read_bytes()
    if digest(admission) != flow["admission_sha256"]:
        reject("admission custody failure")
    return flow

def advance(jobdir, flow, new_state, evidence):
    if STATES.index(new_state) != STATES.index(flow["state"]) + 1:
        reject("nonmonotonic transition")
    row = {"from": flow["state"], "to": new_state, "at_utc": utc_now(),
           "evidence": evidence}
    flow["state"] = new_state
    flow["events"].append(row)
    flow["updated_at_utc"] = row["at_utc"]
    checkpoint(jobdir, flow)
    return {"state": new_state, "job": flow["job_id"], "evidence": evidence}

def execute(command):
    p = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=90)
    if p.returncode:
        reject("bounded subprocess failed: " + (p.stderr[-450:] or p.stdout[-450:]))
    return p.stdout

def init(args):
    receipt_raw = args.admission.read_bytes()
    if len(receipt_raw) > 40_000:
        reject("oversized admission receipt")
    receipt = json.loads(receipt_raw)
    jid = receipt.get("job_id", "")
    vid = receipt.get("video_id", "")
    if (receipt.get("schema") != "ghostmesh.reasonpack.mail-job.v1"
            or receipt.get("status") != "admitted-awaiting-acquisition"
            or not isinstance(jid, str) or not HEX64.fullmatch(jid)
            or not isinstance(vid, str) or not VIDEO.fullmatch(vid)
            or receipt.get("publication_authority") is not False
            or receipt.get("email_dispatch_authority") is not False):
        reject("invalid admitted request")
    # Directory is provisioned without widening access to any other job.
    args.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = args.root / jid
    if target.exists():
        flow = state(target)
        if flow["admission_sha256"] != digest(receipt_raw):
            reject("job ID reused with changed admission")
        return {"state": flow["state"], "job": jid, "status": "duplicate"}
    target.mkdir(mode=0o700)
    protect_write(target / "admission.json", receipt_raw)
    flow = {"schema": SCHEMA, "job_id": jid, "video_id": vid,
            "admission_sha256": digest(receipt_raw),
            "state": "admitted", "events": [],
            "created_at_utc": utc_now(), "updated_at_utc": utc_now(),
            "publication_authority": False, "dispatch_authority": False}
    checkpoint(target, flow)
    return {"state": "admitted", "job": jid, "status": "created"}

def verify_source(args):
    jobdir = args.job
    fd = lock_job(jobdir)
    try:
        flow = state(jobdir, "admitted")
        if not args.pack.is_dir() or args.pack.is_symlink():
            reject("invalid source directory")
        execute([str(ROOT / "bin/reasonpack"), "verify", str(args.pack)])
        raw = (args.pack / "manifest.json").read_bytes()
        manifest = json.loads(raw)
        if manifest.get("schema") != "ghostmesh-reasoning-pack-v1" or manifest.get("fixture"):
            reject("synthetic source packs cannot advance a live mail job")
        module = import_script("reader-edition")
        url, vid = module.safe_url(manifest.get("sourceUrl"), youtube_only=True)
        source = data(args.pack / "source.json")
        if vid != flow["video_id"] or source.get("id") != vid:
            reject("source video ID does not match email job")
        ref = {"pack_path": str(args.pack.resolve()),
               "manifest_sha256": digest(raw),
               "transcript_sha256": digest((args.pack / "transcript.txt").read_bytes()),
               "source_url": url}
        protect_write(jobdir / "source-reference.json", (json.dumps(ref, sort_keys=True)+"\n").encode())
        return advance(jobdir, flow, "source-verified", ref)
    finally:
        os.close(fd)

def import_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "ops" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def verify_source_unchanged(jobdir):
    ref = data(jobdir / "source-reference.json")
    pack = Path(ref["pack_path"])
    execute([str(ROOT / "bin/reasonpack"), "verify", str(pack)])
    if (digest((pack / "manifest.json").read_bytes()) != ref["manifest_sha256"]
            or digest((pack / "transcript.txt").read_bytes()) != ref["transcript_sha256"]):
        reject("source changed since admission")
    return pack, ref

def prepare_research(args):
    fd = lock_job(args.job)
    try:
        flow = state(args.job, "source-verified")
        pack, ref = verify_source_unchanged(args.job)
        cmd = [sys.executable, str(ROOT / "ops/editorial-packet.py"),
               "--pack", str(pack), "--out", str(args.job / "research-input.json")]
        if (pack/"transcript.txt").stat().st_size > 32_000:
            segdir=args.job/"segments"
            if segdir.exists():
                execute([sys.executable,str(ROOT/"ops/longform-segments.py"),"verify",
                         "--transcript",str(pack/"transcript.txt"),"--segments",str(segdir)])
            else:
                execute([sys.executable,str(ROOT/"ops/longform-segments.py"),"build",
                         "--pack",str(pack),"--out",str(segdir)])
            cmd += ["--segments",str(segdir)]
        for work in args.public_work:
            cmd += ["--work", str(work)]
        execute(cmd)
        packet_raw = (args.job / "research-input.json").read_bytes()
        packet = json.loads(packet_raw)
        if (packet.get("transcript_sha256") != ref["transcript_sha256"]
                or packet.get("source_manifest_sha256") != ref["manifest_sha256"]):
            reject("research packet source custody mismatch")
        return advance(args.job, flow, "awaiting-research",
                       {"research_packet_sha256": digest(packet_raw),
                        "transcript_mode":packet.get("transcript_mode"),
                        "segment_count":packet.get("segment_count"),
                        "public_works": len(packet.get("public_owner_reviewed_thesis_context", []))})
    finally:
        os.close(fd)

def collect_evidence(args):
    fd = lock_job(args.job)
    try:
        flow = state(args.job, "awaiting-research")
        verify_source_unchanged(args.job)
        research_input = args.job / "research-input.json"
        expected = flow["events"][-1]["evidence"]["research_packet_sha256"]
        if digest(research_input.read_bytes()) != expected:
            reject("research input changed before evidence admission")
        capture_status="MANUAL_REGISTRY_ONLY"
        if bool(args.capture_dir) != bool(args.catalog):
            reject("capture evidence and approved catalog must be provided together")
        if args.capture_dir:
            if args.registry.resolve()!= (args.capture_dir/"research-evidence.json").resolve():
                reject("requested registry does not match pinned capture directory")
            collector=import_script("public-source-capture")
            proof=collector.verify_capture(research_input,args.catalog,args.capture_dir)
            if proof.get("registry_sha256") != digest(args.registry.read_bytes()):
                reject("capture receipt not bound to exact research registry")
            capture_status="SOURCE_BYTES_VERIFIED"
        script = import_script("research-evidence")
        record = script.verified_register(args.registry, research_input)
        raw = args.registry.read_bytes()
        protect_write(args.job / "research-evidence.json", raw)
        return advance(args.job, flow, "research-evidence-verified",
                       {"evidence_registry_sha256": digest(raw),
                        "registered_sources": len(record["sources"]),
                        "capture_status": capture_status,
                        "independent_semantic_review": "NOT_PERFORMED"})
    finally:
        os.close(fd)

def prepare_model(args):
    fd = lock_job(args.job)
    try:
        state(args.job, "research-evidence-verified")
        verify_source_unchanged(args.job)
        command=[sys.executable,str(ROOT/"ops/research-composer.py"),"prepare",
                 "--packet",str(args.job/"research-input.json"),
                 "--registry",str(args.job/"research-evidence.json"),
                 "--out",str(args.job/"composition")]
        if (args.job/"segments").exists():
            command += ["--segments",str(args.job/"segments")]
        execute(command)
        receipt=data(args.job/"composition"/"composition-receipt.json")
        if receipt.get("status")!="model-input-ready-not-invoked":
            reject("model handoff failed")
        return {"status":"research-prompt-ready","job":state(args.job)["job_id"],
                "model_invoked":False,"receipt":str(args.job/"composition"/"composition-receipt.json")}
    finally:
        os.close(fd)

def ingest_analysis(args):
    fd = lock_job(args.job)
    try:
        flow = state(args.job, "research-evidence-verified")
        verify_source_unchanged(args.job)
        if not (args.job / "research-input.json").is_file():
            reject("missing research handoff")
        expected = flow["events"][-2]["evidence"]["research_packet_sha256"]
        if digest((args.job / "research-input.json").read_bytes()) != expected:
            reject("research input has changed")
        registry = args.job / "research-evidence.json"
        if digest(registry.read_bytes()) != flow["events"][-1]["evidence"]["evidence_registry_sha256"]:
            reject("evidence registry changed after validation")
        composition=data(args.job/"composition"/"composition-receipt.json")
        if composition.get("status")!="model-input-ready-not-invoked":
            reject("bounded composition not prepared")
        if (composition.get("research_packet_sha256")!=digest((args.job/"research-input.json").read_bytes())
                or composition.get("evidence_registry_sha256")!=digest(registry.read_bytes())
                or composition.get("model_prompt_sha256")!=digest((args.job/"composition"/"model-prompt.json").read_bytes())
                or composition.get("model_schema_sha256")!=digest((args.job/"composition"/"analysis-schema.json").read_bytes())):
            reject("prepared model context has changed")
        raw = args.analysis.read_bytes()
        if len(raw)>400_000:
            reject("analysis too large")
        analysis=json.loads(raw)
        mod=import_script("reader-edition")
        mod.load_analysis(args.analysis)
        if analysis.get("video_id") != flow["video_id"]:
            reject("wrong video in analysis")
        research = import_script("research-evidence")
        corroboration = research.assert_supported_claims(analysis, research.verified_register(registry, args.job / "research-input.json"))
        validation_path=args.job/"research-validation-receipt.json"
        validation_cmd=[sys.executable,str(ROOT/"ops/research-composer.py"),"validate",
                 "--packet",str(args.job/"research-input.json"),
                 "--registry",str(registry),
                 "--candidate",str(args.analysis),
                 "--out",str(validation_path)]
        if composition.get("transcript_mode")=="segmented":
            validation_cmd.extend([
                 "--composition",str(args.job/"composition"),
                 "--segment-results",str(args.job/"segment-results"),
                 "--synthesis",str(args.job/"synthesis")])
        execute(validation_cmd)
        if (data(validation_path).get("semantic_review")!="NOT_ATTESTED" or
                data(validation_path).get("candidate_sha256")!=digest(raw)):
            reject("machine-generated research cannot self-attest or modify source")
        # Provenance is not equivalent to editorial verification; HOLD is retained.
        protect_write(args.job / "analysis-unreviewed.json", raw)
        return advance(args.job, flow, "analysis-unreviewed",
                       {"analysis_sha256": digest(raw), "editorial_review": "required",
                        "citation_register_bound": corroboration["bound_citations"],
                        "all_segment_coverage_sha256":
                           data(validation_path).get("all_segment_coverage_sha256"),
                        "semantic_source_review": "NOT_ATTESTED"})
    finally:
        os.close(fd)

def render(args):
    fd = lock_job(args.job)
    try:
        flow = state(args.job, "analysis-unreviewed")
        pack, _ = verify_source_unchanged(args.job)
        analysis = args.job / "analysis-unreviewed.json"
        if digest(analysis.read_bytes()) != flow["events"][-1]["evidence"]["analysis_sha256"]:
            reject("analysis custody changed")
        execute([sys.executable, str(ROOT / "ops/reader-edition.py"),
                 "--pack", str(pack), "--analysis", str(analysis),
                 "--out", str(args.job / "reader")])
        reader = data(args.job / "reader" / "reader-receipt.json")
        if reader.get("analysis_sha256") != digest(analysis.read_bytes()) or reader.get("state") != "private-draft":
            reject("rendered reader receipt invalid")
        return advance(args.job, flow, "reader-private-draft",
                       {"reader_html_sha256": reader["reader_html_sha256"], "publication": "not-authorized"})
    finally:
        os.close(fd)

def draft(args):
    fd = lock_job(args.job)
    try:
        flow = state(args.job, "reader-private-draft")
        analysis = args.job / "analysis-unreviewed.json"
        readerreceipt = args.job / "reader" / "reader-receipt.json"
        receipt=data(readerreceipt)
        if (receipt.get("reader_html_sha256") != flow["events"][-1]["evidence"]["reader_html_sha256"]):
            reject("reader receipt drift")
        execute([sys.executable, str(ROOT / "ops/mail-reasonpack.py"), "draft",
                 "--from-email", args.from_email,
                 "--job", str(args.job / "admission.json"),
                 "--reader-receipt", str(readerreceipt),
                 "--analysis", str(analysis), "--out", str(args.job / "draft.eml")])
        return advance(args.job, flow, "email-private-draft",
                       {"draft_sha256": digest((args.job / "draft.eml").read_bytes()),
                        "gmail_sent": False, "public_release": False})
    finally:
        os.close(fd)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="step", required=True)
    initp = sub.add_parser("init"); initp.add_argument("--admission", type=Path, required=True); initp.add_argument("--root", type=Path, required=True)
    source = sub.add_parser("source"); source.add_argument("--job", type=Path, required=True); source.add_argument("--pack", type=Path, required=True)
    research = sub.add_parser("research"); research.add_argument("--job", type=Path, required=True); research.add_argument("--public-work", type=Path, action="append", default=[])
    evidence = sub.add_parser("evidence"); evidence.add_argument("--job",type=Path,required=True); evidence.add_argument("--registry",type=Path,required=True)
    evidence.add_argument("--capture-dir",type=Path)
    evidence.add_argument("--catalog",type=Path)
    model = sub.add_parser("compose"); model.add_argument("--job", type=Path, required=True)
    analysis = sub.add_parser("analysis"); analysis.add_argument("--job", type=Path, required=True); analysis.add_argument("--analysis", type=Path, required=True)
    read = sub.add_parser("render"); read.add_argument("--job", type=Path, required=True)
    draftp = sub.add_parser("draft"); draftp.add_argument("--job", type=Path, required=True); draftp.add_argument("--from-email", required=True)
    statusp = sub.add_parser("status"); statusp.add_argument("--job", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.step == "init": result=init(args)
        elif args.step == "source": result=verify_source(args)
        elif args.step == "research": result=prepare_research(args)
        elif args.step == "evidence": result=collect_evidence(args)
        elif args.step == "compose": result=prepare_model(args)
        elif args.step == "analysis": result=ingest_analysis(args)
        elif args.step == "render": result=render(args)
        elif args.step == "draft": result=draft(args)
        else:
            flow=state(args.job)
            result={"state":flow["state"],"job":flow["job_id"],"events":flow["events"]}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print("HOLD: "+str(error), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
