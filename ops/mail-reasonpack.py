#!/usr/bin/env python3
"""Staged authenticated GhostMesh mail handoff to ReasonPack. No network or send calls."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse, parse_qs

SCHEMA = "ghostmesh.reasonpack.mail-intake.v1"
YOUTUBE = re.compile(r"https://(?:www\.|m\.)?(?:youtube\.com/watch\?[^\s<>]+|youtu\.be/[^\s<>]+)", re.I)
INTENT = re.compile(r"\b(?:reason[\s-]?pack|reasoning[\s-]?pack)\b", re.I)
MESSAGE_ID = re.compile(r"^<[^<>\r\n]{3,220}>$")
VID = re.compile(r"^[A-Za-z0-9_-]{11}$")
HMAC_ENV = "REASONPACK_MAIL_INGEST_KEY"

def reject(reason):
    raise ValueError(reason)

def now():
    return datetime.now(timezone.utc)

def canonical_record(data):
    payload = {k:v for k,v in data.items() if k != "auth_tag"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def validate_envelope(envelope, key: bytes, allowed_senders):
    if envelope.get("schema") != SCHEMA:
        reject("wrong mail gateway schema")
    tag = envelope.get("auth_tag")
    if not isinstance(tag, str) or not re.fullmatch(r"[0-9a-f]{64}",tag):
        reject("signed gateway envelope required")
    actual = hmac.new(key, canonical_record(envelope), "sha256").hexdigest()
    if not hmac.compare_digest(tag, actual):
        reject("invalid mail gateway authentication")
    if envelope.get("gateway_authenticated") is not True or envelope.get("policy_admitted") is not True:
        reject("mail auth and policy admission required")
    sender = envelope.get("verified_sender","")
    if not isinstance(sender,str) or parseaddr(sender)[1].lower() != sender.lower() or "@" not in sender:
        reject("invalid authenticated sender")
    sender = sender.lower()
    if sender not in allowed_senders:
        reject("sender not allowlisted")
    gmail_id = envelope.get("gmail_id")
    gmail_thread_id = envelope.get("gmail_thread_id")
    if (gmail_id is None) != (gmail_thread_id is None):
        reject("gmail source and thread must be paired")
    if gmail_id is not None:
        if not isinstance(gmail_id, str) or not re.fullmatch(r"[0-9a-f]{10,32}", gmail_id):
            reject("invalid authenticated gmail source ID")
        if not isinstance(gmail_thread_id, str) or not 0 < len(gmail_thread_id) < 256 or any(c in gmail_thread_id for c in "\r\n"):
            reject("invalid authenticated gmail thread ID")
    message_id = envelope.get("message_id","")
    if not isinstance(message_id,str) or not MESSAGE_ID.fullmatch(message_id):
        reject("invalid message-id")
    issued = envelope.get("issued_at_utc","")
    try:
        issued_dt = datetime.fromisoformat(issued.replace("Z","+00:00"))
        if issued_dt.tzinfo is None or not now()-timedelta(days=7) <= issued_dt <= now()+timedelta(minutes=5):
            reject("gateway envelope expired or issued in future")
    except (ValueError, TypeError):
        reject("invalid gateway timestamp")
    subject = envelope.get("subject","")
    body = envelope.get("body_text","")
    if not isinstance(subject,str) or len(subject)>240 or "\n" in subject or "\r" in subject:
        reject("invalid mail subject")
    if not isinstance(body,str) or not (0<len(body)<=25000):
        reject("invalid mail body")
    return sender, message_id, subject, body

def parse_intent(body):
    original = []
    for line in body.splitlines():
        low = line.lstrip().lower()
        if line.lstrip().startswith(">") or low.startswith(("on ", "from: ", "sent: ", "-----original message", "begin forwarded message")):
            break
        original.append(line)
    fresh = "\n".join(original)
    if not INTENT.search(fresh):
        reject("no explicit ReasonPack intent in fresh message")
    url_matches = [m.group(0).rstrip(".,;!?)'\"") for m in YOUTUBE.finditer(fresh)]
    video_ids = set()
    for match in url_matches:
        u = urlparse(match)
        host = (u.hostname or "").lower()
        v = u.path.strip("/") if host=="youtu.be" else parse_qs(u.query).get("v",[""])[0] if u.path=="/watch" else ""
        if not VID.fullmatch(v):
            reject("malformed YouTube source URL: complete video ID required")
        video_ids.add(v)
    if len(video_ids)!=1:
        reject("request must contain exactly one distinct valid YouTube source")
    vid = next(iter(video_ids))
    return vid, "https://www.youtube.com/watch?v="+vid

def atomic_private(path:Path, data:bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(data)

def admit(args):
    raw=args.envelope.read_bytes()
    if len(raw)>35000:
        reject("envelope too large")
    key=os.environ.get(HMAC_ENV,"").encode()
    if len(key)<32:
        reject("mail ingestion signing key not commissioned")
    allowed={s.strip().lower() for s in args.allow_sender if s.strip()}
    if not allowed:
        reject("empty authorized sender list")
    sender,message_id,subject,body=validate_envelope(json.loads(raw),key,allowed)
    vid,url=parse_intent(body)
    parsed_envelope = json.loads(raw)
    job_id=sha256((sender+"\0"+str(parsed_envelope.get("gmail_id") or message_id)+"\0"+vid).encode()).hexdigest()
    canonical_intent = {k:v for k,v in parsed_envelope.items() if k not in ("auth_tag", "issued_at_utc")}
    intent_fingerprint = sha256(json.dumps(canonical_intent, sort_keys=True, separators=(",",":"), ensure_ascii=True).encode()).hexdigest()
    input_envelope = parsed_envelope
    receipt={"schema":"ghostmesh.reasonpack.mail-job.v1","job_id":job_id,
             "admission_intent_sha256":intent_fingerprint,
             "gmail_id": input_envelope.get("gmail_id"), "gmail_thread_id": input_envelope.get("gmail_thread_id"),
             "sender":sender,"message_id":message_id,"subject":subject,"video_id":vid,
             "source_url":url,"status":"admitted-awaiting-acquisition",
             "admission_scope":"mail-gateway-signed-and-sender-allowlisted",
             "publication_authority":False,"email_dispatch_authority":False,
             "created_at_utc":now().isoformat()}
    path=args.out/job_id[:2]/(job_id+".json")
    try:
        atomic_private(path,(json.dumps(receipt,indent=2,sort_keys=True)+"\n").encode())
        status="admitted"
    except FileExistsError:
        recorded=json.loads(path.read_text())
        if (recorded.get("job_id") != job_id or recorded.get("video_id") != vid
                or recorded.get("admission_intent_sha256") != intent_fingerprint):
            reject("conflicting existing mail admission receipt")
        status="duplicate-ignored"
    print(json.dumps({"result":status,"job_id":job_id,"receipt_path":str(path)}))

def draft(args):
    receipt=json.loads(args.job.read_text())
    reader=json.loads(args.reader_receipt.read_text())
    analysis=json.loads(args.analysis.read_text())
    if receipt.get("schema")!="ghostmesh.reasonpack.mail-job.v1" or reader.get("state")!="private-draft":
        reject("invalid draft input state")
    if receipt.get("video_id")!=analysis.get("video_id"):
        reject("mail source and analysis source mismatch")
    if reader.get("analysis_sha256")!=sha256(args.analysis.read_bytes()).hexdigest():
        reject("analysis edition digest mismatch")
    html_path=args.reader_receipt.with_name("index.html")
    if sha256(html_path.read_bytes()).hexdigest()!=reader.get("reader_html_sha256"):
        reject("reader edition drift detected")
    msg=EmailMessage()
    sender=args.from_email.strip().lower()
    if parseaddr(sender)[1] != sender or "@" not in sender or "\n" in sender or "\r" in sender:
        reject("invalid configured From identity")
    msg["From"]=sender
    msg["To"]=receipt["sender"]
    msg["Subject"]="Re: " + receipt.get("subject","ReasonPack request")
    msg["In-Reply-To"]=receipt["message_id"]
    msg["References"]=receipt["message_id"]
    msg["X-GhostMesh-Draft-Only"]="true"
    th=analysis["thesis"]
    text=("GhostMesh ReasonPack: "+analysis["headline"]+"\n\n"+
          "Executive verdict\n"+analysis["executive"]+"\n\n"+
          "GhostMesh thesis: "+th["title"]+"\n"+th["argument"]+"\n\n"+
          "Original video: "+receipt["source_url"]+"\n\n"+
          "The complete Reader Edition is attached for private review. "+
          "This is a staged draft, not a sent email or public publication.\n\n"+
          "GhostMesh\n")
    msg.set_content(text)
    msg.add_attachment(html_path.read_bytes(), maintype="text", subtype="html", filename="GhostMesh-ReasonPack-Reader.html")
    if args.out.exists():
        reject("draft exists; do not overwrite")
    atomic_private(args.out,msg.as_bytes())
    print(json.dumps({"result":"draft-only","output":str(args.out),"bytes":args.out.stat().st_size}))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    ac=sub.add_parser("admit")
    ac.add_argument("--envelope",type=Path,required=True)
    ac.add_argument("--allow-sender",action="append",required=True)
    ac.add_argument("--out",type=Path,required=True)
    dr=sub.add_parser("draft")
    dr.add_argument("--from-email",required=True)
    dr.add_argument("--job",type=Path,required=True)
    dr.add_argument("--reader-receipt",type=Path,required=True)
    dr.add_argument("--analysis",type=Path,required=True)
    dr.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    try:
        if args.command=="admit":admit(args)
        else:draft(args)
    except (ValueError,FileNotFoundError,PermissionError,json.JSONDecodeError,OSError) as ex:
        print("REJECTED: "+str(ex),file=sys.stderr)
        return 2
    return 0
if __name__=="__main__":
    raise SystemExit(main())
