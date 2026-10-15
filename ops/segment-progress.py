#!/usr/bin/env python3
"""Immutable per-segment ReasonPack progress receipts, without a whole-job timeout.

Accepts untrusted candidate observations only. No model is invoked, and a
complete set of candidates is NOT an independent review or final answer.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

SCHEMA="ghostmesh.reasonpack.segment-candidate.v1"
RECEIPT="ghostmesh.reasonpack.segment-progress.v1"
SHA=re.compile(r"^[0-9a-f]{64}$")

def deny(s):raise ValueError(s)
def digest(raw):return sha256(raw).hexdigest()

def load_composition(folder):
    r=json.loads((folder/"composition-receipt.json").read_text("utf-8"))
    if r.get("schema")!="ghostmesh.reasonpack.composition.v1" or r.get("transcript_mode")!="segmented":
        deny("not a segmented composition")
    parts=r.get("segment_prompt_receipts")
    if not isinstance(parts,list) or not parts:deny("no segment prompt inventory")
    for i,row in enumerate(parts):
        if row.get("index")!=i or row.get("path")!=f"segment-{i:06d}.json" or not SHA.fullmatch(row.get("prompt_sha256","")):
            deny("invalid segment prompt ordering")
        payload=(folder/"segment-prompts"/row["path"])
        if payload.is_symlink() or digest(payload.read_bytes())!=row["prompt_sha256"]:
            deny("segment prompt changed after preparation")
        expected_schema=f"segment-{i:06d}.schema.json"
        if row.get("schema_path")!=expected_schema or not SHA.fullmatch(row.get("schema_sha256","")):
            deny("missing per-segment output contract")
        schema=folder/"segment-schemas"/expected_schema
        if schema.is_symlink() or digest(schema.read_bytes())!=row["schema_sha256"]:
            deny("per-segment output schema changed")
    return r,parts

def check_candidate(record,entry):
    if not isinstance(record,dict) or record.get("schema")!=SCHEMA:
        deny("invalid candidate schema")
    if record.get("segment_index")!=entry["index"]:
        deny("candidate points to wrong segment index")
    if record.get("segment_sha256")!=entry["segment_sha256"] or record.get("prompt_sha256")!=entry["prompt_sha256"]:
        deny("candidate refers to wrong exact segment/prompt")
    observations=record.get("observations")
    if not isinstance(observations,list) or not 1<=len(observations)<=12:deny("candidate observations missing or oversized")
    for v in observations:
        if not isinstance(v,str) or not v.strip() or len(v)>1000:deny("invalid segment observation")
    if record.get("source_truth_attested") is not False or record.get("final_answer_authorized") is not False:
        deny("candidate cannot self-authorize research conclusion")
    if set(record)-{"schema","segment_index","segment_sha256","prompt_sha256","observations",
                     "source_truth_attested","final_answer_authorized"}:
        deny("unexpected candidate operational field")

def stage(composition,results,index,candidate):
    r,parts=load_composition(composition)
    if not isinstance(index,int) or index<0 or index>=len(parts):deny("segment index out of range")
    row=parts[index]
    raw=candidate.read_bytes()
    if len(raw)>180_000:deny("oversized candidate")
    parsed=json.loads(raw)
    check_candidate(parsed,row)
    results.mkdir(parents=True,mode=0o700,exist_ok=True)
    if results.is_symlink():deny("symlinked progress root")
    path=results/f"segment-{index:06d}.json"
    if path.exists() or path.is_symlink():
        if path.read_bytes()!=raw:
            deny("conflicting candidate on already staged segment")
        return {"status":"already-staged","segment":index}
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    return {"status":"staged-unreviewed","segment":index,"candidate_sha256":digest(raw)}

def status(composition,results):
    receipt,parts=load_composition(composition)
    done=[]
    missing=[]
    expected={f"segment-{i:06d}.json" for i in range(len(parts))}
    if results.exists():
        if results.is_symlink() or not results.is_dir():deny("invalid progress directory")
        if {x.name for x in results.iterdir()}-expected:deny("unexpected segment result")
    for i,row in enumerate(parts):
        path=results/f"segment-{i:06d}.json"
        if not path.exists():
            missing.append(i);continue
        if path.is_symlink() or not path.is_file():deny("invalid candidate member")
        raw=path.read_bytes()
        if len(raw)>180_000:deny("oversized candidate member")
        candidate=json.loads(raw)
        check_candidate(candidate,row)
        done.append({"index":i,"candidate_sha256":digest(raw)})
    return {"schema":RECEIPT,"segments_total":len(parts),"segments_staged":len(done),
            "completed_indices":[x["index"] for x in done],"missing_indices":missing,
            "candidate_receipts":done,
            "status":"all-candidates-staged-unreviewed" if not missing else "partial-resumable",
            "model_provider":"UNKNOWN","measured_tokens":None,
            "actual_billed_cost":None,"semantic_review":"NOT_ATTESTED",
            "public_release":False,"email_delivery":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="operation",required=True)
    for cmd in ("stage","status"):
        a=sub.add_parser(cmd)
        a.add_argument("--composition",type=Path,required=True)
        a.add_argument("--results",type=Path,required=True)
        if cmd=="stage":
            a.add_argument("--index",type=int,required=True)
            a.add_argument("--candidate",type=Path,required=True)
    a=p.parse_args()
    try:
        res=stage(a.composition,a.results,a.index,a.candidate) if a.operation=="stage" else status(a.composition,a.results)
        print(json.dumps(res,sort_keys=True));return 0
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        print("HOLD: "+str(exc),file=sys.stderr);return 2

if __name__=="__main__":raise SystemExit(main())
