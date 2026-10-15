#!/usr/bin/env python3
"""Trusted in-process adapter AFTER GhostMesh public Gmail authentication.

This module is not a raw-email authenticator. The caller must have already
executed gm_public_responder.validate_public_email(), identity + policy admission,
and existing journal reservation. It DOES NOT call the mail provider or send mail.
"""
from __future__ import annotations
import hmac
import json
from datetime import datetime, timezone
from email.utils import parseaddr
from hashlib import sha256
from pathlib import Path
import re

SIGNING_SCHEMA = "ghostmesh.reasonpack.mail-intake.v1"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
GMAIL_ID = re.compile(r"^[0-9a-f]{10,32}$")
REQUIRED = frozenset({"gmail_id","gmail_thread_id","sender","message_id_header","subject","body"})
MAX_BODY_BYTES = 25000

class AdapterDenied(ValueError): pass

def require(test, text):
    if not test: raise AdapterDenied(text)

def normalize_verified_item(item:dict, *, admitted:bool, owner_only:bool=True,
                            owner_sender:str|None=None, key:bytes,
                            now_utc:str|None=None):
    """Return HMAC-signed envelope only from a verified, policy-admitted item.

    An unprivileged caller supplying fake item fields can forge an envelope IF
    it holds the signing key. Thus the key must remain only at the authentic
    admitted mail boundary, not the public worker/renderer.
    """
    require(isinstance(item,dict), "validated mail item required")
    require(REQUIRED.issubset(item), "verified mail item lacks necessary fields")
    require(admitted is True, "mail admission not established")
    sender=item["sender"]
    require(isinstance(sender,str) and parseaddr(sender)[1] == sender and "@" in sender,
            "invalid sender")
    sender=sender.lower()
    if owner_only:
        require(owner_sender and sender == owner_sender.lower(),
                "owner-canary only until recipient authorization commissioned")
    gid=item["gmail_id"]
    require(isinstance(gid,str) and GMAIL_ID.fullmatch(gid),"invalid gmail source ID")
    thread=item["gmail_thread_id"]
    require(isinstance(thread,str) and 0<len(thread)<256
            and not any(c in thread for c in "\r\n"),"invalid gmail thread ID")
    msgid=item["message_id_header"]
    require(isinstance(msgid,str) and re.fullmatch(r"<[^<>\r\n]{3,220}>",msgid),
            "RFC Message-ID required for present draft path")
    subject=item["subject"]
    require(isinstance(subject,str) and 0<len(subject)<=240
            and "\r" not in subject and "\n" not in subject,"invalid subject")
    body=item["body"]
    require(isinstance(body,str) and 0<len(body.encode("utf-8"))<=MAX_BODY_BYTES,
            "missing or oversize body")
    require(isinstance(key,bytes) and len(key)>=32,"uncommissioned gateway signing key")
    envelope={"schema":SIGNING_SCHEMA, "verified_sender":sender,
             "gmail_id":gid,"gmail_thread_id":thread,
             "message_id":msgid,"subject":subject,"body_text":body,
             "gateway_authenticated":True,"policy_admitted":True,
             "admission_scope":"owner-only" if owner_only else "sender-policy",
             "issued_at_utc": now_utc or datetime.now(timezone.utc).isoformat()}
    canonical=json.dumps(envelope,sort_keys=True,separators=(",",":"),
                         ensure_ascii=True).encode()
    envelope["auth_tag"]=hmac.new(key,canonical,"sha256").hexdigest()
    return envelope

def validate_handoff_contract(envelope:dict, *, sender:str, gmail_id:str,
                              gmail_thread_id:str):
    """Caller must reconcile the receipt against provider-assigned email IDs."""
    require(envelope["verified_sender"]==sender.lower(), "mail recipient mismatch")
    require(envelope["gmail_id"]==gmail_id, "source Gmail ID mismatch")
    require(envelope["gmail_thread_id"]==gmail_thread_id, "Gmail thread mismatch")
    return True
