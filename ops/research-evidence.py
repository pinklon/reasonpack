#!/usr/bin/env python3
"""Offline evidence register for a ReasonPack editorial analysis.

Public sources are supplied by a separately authorized retrieval process.
A record of a URL is not proof the linked claim is true; the register binds
source identity and excerpt bytes to the job so an analyzer cannot invent
or silently swap corroboration. No HTTP or model calls in this module.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from ipaddress import ip_address

SCHEMA = "ghostmesh.reasonpack.evidence.v1"
SOURCE_ID = re.compile(r"^src-[0-9a-z]{4,24}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
ISO_UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?\+00:00$")

def reject(message:str):
    raise ValueError(message)

def sha(raw:bytes)->str:
    return sha256(raw).hexdigest()

def safe_public_url(s):
    if not isinstance(s,str) or not(12 <= len(s) <= 2048):
        reject("source URL missing or too long")
    u=urlsplit(s)
    host=(u.hostname or "").lower().strip(".")
    if (u.scheme != "https" or not host or u.port not in (None,443)
            or u.username or u.password or u.fragment or
            host in ("localhost","localhost.localdomain")
            or host.endswith((".local",".internal",".test"))
            or re.search(r"[\s\x00-\x1f]",s)):
        reject("unsupported public evidence URL")
    try:
        ip_address(host)
        reject("IP literal not permitted in citation URL")
    except ValueError as exc:
        if str(exc)=="IP literal not permitted in citation URL":
            raise
    if "." not in host or host.startswith("-"):
        reject("public hostname required")
    return s

def ensure_text(d,k,limit):
    v=d.get(k)
    if not isinstance(v,str) or not v.strip() or len(v)>limit:
        reject(f"invalid {k}")
    return v.strip()

def verified_register(path:Path, packet_path:Path):
    packet=json.loads(packet_path.read_text("utf-8"))
    if packet.get("schema")!="ghostmesh.reasonpack.editorial-packet.v1":
        reject("wrong bound research input")
    manifest_digest=packet.get("source_manifest_sha256")
    transcript_digest=packet.get("transcript_sha256")
    if not (isinstance(manifest_digest,str) and HASH.fullmatch(manifest_digest)
            and isinstance(transcript_digest,str) and HASH.fullmatch(transcript_digest)):
        reject("invalid canonical evidence digests")
    item=json.loads(path.read_text("utf-8"))
    if item.get("schema")!=SCHEMA or item.get("source_manifest_sha256")!=manifest_digest or item.get("transcript_sha256")!=transcript_digest:
        reject("source registry is not bound to the canonical ReasonPack")
    sources=item.get("sources")
    if not isinstance(sources,list) or not (1<=len(sources)<=24):
        reject("require 1-24 collected public sources")
    ids=set()
    urls=set()
    for s in sources:
        if not isinstance(s,dict):
            reject("malformed public source")
        sid=ensure_text(s,"id",32)
        if not SOURCE_ID.fullmatch(sid) or sid in ids:
            reject("duplicate or invalid source ID")
        ids.add(sid)
        url=safe_public_url(ensure_text(s,"url",2048))
        if url in urls: reject("duplicate public source URL")
        urls.add(url)
        ensure_text(s,"title",300)
        ensure_text(s,"publisher",180)
        ensure_text(s,"excerpt",4000)
        if s.get("evidence_type") not in ("primary","independent","contemporaneous","context"):
            reject("unknown evidence type")
        stamp=ensure_text(s,"retrieved_at_utc",40)
        if not ISO_UTC.fullmatch(stamp):
            reject("source lacks UTC retrieval timestamp")
        try: datetime.fromisoformat(stamp)
        except ValueError: reject("invalid retrieval timestamp")
        expected=sha(s["excerpt"].encode("utf-8"))
        if s.get("excerpt_sha256") != expected:
            reject("excerpt checksum mismatch")
    return item

def assert_supported_claims(analysis:dict,registry:dict):
    """Evidence binding is syntactic; human/source review is still required."""
    urls={s["url"]:s for s in registry["sources"]}
    def bound_citation(cited):
        if not isinstance(cited,dict) or cited.get("url") not in urls:
            reject("generated claim cites an unregistered evidence URL")
        source=urls[cited["url"]]
        if cited.get("label")!=source["title"]:
            reject("citation label differs from registered source title")
        return source
    linked=0
    for c in analysis.get("claims",[]):
        verdict=c.get("verdict")
        if verdict in ("supported","partially-supported","disputed"):
            citations=c.get("sources") or []
            if not citations:
                reject(f"{verdict} claim missing evidence")
            # A supported verdict requires an independently collected source;
            # a title and invented URL from the generating model do not count.
            for cited in citations:
                source=bound_citation(cited)
                if source["evidence_type"]=="context" and verdict=="supported":
                    reject("context-only evidence cannot establish a supported claim")
                linked+=1
        else:
            for cited in c.get("sources",[]):
                bound_citation(cited)
    return {"registered_sources":len(urls),"bound_citations":linked,
            "semantic_source_review":"not-attested",
            "automated_publication_authority":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet",type=Path,required=True)
    p.add_argument("--registry",type=Path,required=True)
    p.add_argument("--analysis",type=Path)
    args=p.parse_args()
    try:
        r=verified_register(args.registry,args.packet)
        result={"result":"registry-verified","register_sha256":sha(args.registry.read_bytes()),
                "registered_sources":len(r["sources"])}
        if args.analysis:
            analysis=json.loads(args.analysis.read_text("utf-8"))
            result.update(assert_supported_claims(analysis,r))
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,FileNotFoundError,json.JSONDecodeError) as e:
        print("HOLD: "+str(e),file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
