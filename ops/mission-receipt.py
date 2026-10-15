#!/usr/bin/env python3
"""Private source-only GhostMesh Mission envelope and truthful telemetry projection.

No sender, billing provider, payment processor, frontend publisher, worker or
subscription endpoint. The preview/quote/payment sequence is a future contract.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

SCHEMA="ghostmesh.mission.request.v1"
PROJECTION="ghostmesh.mission.telemetry-projection.v1"
KINDS={"reasonpack","website_preview","research"}
SURFACES={"gmail","slack","owner"}
SHA=re.compile(r"^[0-9a-f]{64}$")

def deny(s):raise ValueError(s)
def digest(raw):return sha256(raw).hexdigest()

def make(kind,surface,source_event_fingerprint,out):
    if kind not in KINDS or surface not in SURFACES:
        deny("invalid mission type or source")
    if not isinstance(source_event_fingerprint,str) or not SHA.fullmatch(source_event_fingerprint):
        deny("source must be a privacy-preserving event SHA-256")
    identity=digest(("ghostmesh.mission.v1\0"+surface+"\0"+source_event_fingerprint+"\0"+kind).encode())
    request={
      "schema":SCHEMA,"mission_id":identity,"kind":kind,"surface":surface,
      "source_event_fingerprint":source_event_fingerprint,
      "request_admission":"NOT_ATTESTED",
      "phase":"proposed-private",
      "artifact_publication_authority":False,"worker_dispatch_authority":False,
      "outgoing_message_authority":False,"customer_payment_authorized":False,
      "payment_provider_connected":False,
      "owner_upfront_spend_approved":False,
      "owner_spend_cap_usd":None,
      "pricing_model":"UNCONFIGURED",
      "customer_quote":None,
      "preview_visibility":"PRIVATE_NOT_DELIVERED",
      "payment_status":"NOT_CONFIGURED",
      "promise_to_deliver":False,
      "source_telemetry_contract":"pinklon/ghostmesh-collab#86",
      "independent_delivery_witness_contract":"pinklon/ghostmesh-collab#117"
    }
    if out.exists():deny("mission receipt exists")
    out.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:json.dump(request,f,indent=2,sort_keys=True);f.write("\n")
    return {"mission_id":identity,"phase":request["phase"],"payment_status":request["payment_status"]}

def project(mission_path,workflow_path):
    mission=json.loads(mission_path.read_text("utf-8"))
    if mission.get("schema")!=SCHEMA or mission.get("payment_provider_connected") is not False:
        deny("invalid or payment-enabled mission receipt")
    records=[]
    if workflow_path:
        flow=json.loads(workflow_path.read_text("utf-8"))
        if flow.get("schema")!="ghostmesh.reasonpack.workflow.v1":
            deny("unknown workflow provenance")
        if mission.get("kind")!="reasonpack":
            deny("workflow type and mission type mismatch")
        for event in flow.get("events",[]):
            if event.get("to") not in (
              "source-verified","awaiting-research","research-evidence-verified",
              "analysis-unreviewed","reader-private-draft","email-private-draft"):
                deny("unsupported workflow stage")
            if not isinstance(event.get("at_utc"),str) or not event.get("at_utc"):
                deny("unattributed stage timing")
            records.append({"stage":event["to"],"observed_transition_at_utc":event["at_utc"],
                 "method":"deterministic-stage-transition",
                 "usage_tokens":"not_applicable",
                 "requested_model":None,"attested_model":None,
                 "estimated_api_equivalent_usd":None,"actual_provider_billed_usd":None,
                 "publisher_witness":"UNKNOWN",
                 "outbound_accepted":"UNKNOWN"})
    return {
      "schema":PROJECTION,"mission_id":mission["mission_id"],
      "kind":mission["kind"],"phase":mission["phase"],
      "stages":records,"completed_transition_count":len(records),
      "ai_invocations":"UNKNOWN",
      "provider_usage":"UNKNOWN",
      "requested_route":None,"verified_backend":None,
      "actual_provider_billed_cost_usd":None,
      "estimated_api_equivalent_cost_usd":None,
      "subscription_credit_attribution":"UNKNOWN",
      "owner_spend_exposure_usd":None,
      "customer_quote":None,
      "customer_charge_usd":None,
      "customer_payment_status":"NOT_CONFIGURED",
      "pre_send_authority":"NOT_GRANTED",
      "provider_delivery_acceptance":"UNKNOWN",
      "inbox_arrival":"NOT_ATTESTED",
      "recipient_visible_telemetry":False,
      "footer_activated":False,"public_reader_published":False,
      "telemetry_authority":"unverified-local-source-projection",
      "cross_system_identity_join_attested":False,
      "source_receipt_citation":"pinklon/ghostmesh-collab#86",
      "witness_dependency":"pinklon/ghostmesh-collab#117"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    init=sub.add_parser("create")
    init.add_argument("--kind",required=True,choices=sorted(KINDS))
    init.add_argument("--surface",required=True,choices=sorted(SURFACES))
    init.add_argument("--event-sha256",required=True)
    init.add_argument("--out",type=Path,required=True)
    view=sub.add_parser("project")
    view.add_argument("--mission",type=Path,required=True)
    view.add_argument("--workflow",type=Path)
    args=p.parse_args()
    try:
        data=(make(args.kind,args.surface,args.event_sha256,args.out)
              if args.command=="create" else project(args.mission,args.workflow))
        print(json.dumps(data,sort_keys=True));return 0
    except (ValueError,TypeError,KeyError,FileNotFoundError,OSError,json.JSONDecodeError) as exc:
        print("HOLD: "+str(exc),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
