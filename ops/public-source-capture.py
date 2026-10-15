#!/usr/bin/env python3
"""Owner-curated, pinned-DNS public HTTPS source capture for ReasonPack.

Never accept unreviewed hostnames or credentials, follow redirects, send cookies,
invoke a model or publish. A source excerpt MUST occur in downloaded source text.
Collected content is still untrusted and semantic claim support is NOT attested.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPSConnection
from ipaddress import ip_address
import json
import os
from pathlib import Path
import re
import signal
import socket
import ssl
import sys
from urllib.parse import urlsplit

MAX_BODY=2_000_000
MAX_TEXT=160_000
MAX_SOURCES=8
HOST_ALLOW=frozenset({
 "openai.com","www.openai.com","www.anthropic.com","anthropic.com",
 "metr.org","www.metr.org","quasiqualia.com","www.quasiqualia.com",
 "github.com","www.github.com"
})
ID=re.compile(r"^src-[0-9a-z]{4,24}$")
HASH=re.compile(r"^[0-9a-f]{64}$")

def fail(reason):
    raise ValueError(reason)
def digest(raw):
    return sha256(raw).hexdigest()
def safe_source(url):
    if not isinstance(url,str) or not 12<=len(url)<=1400:
        fail("source URL size invalid")
    part=urlsplit(url)
    host=(part.hostname or "").lower()
    if (part.scheme!="https" or host not in HOST_ALLOW or part.port not in (None,443)
        or part.username or part.password or part.fragment
        or re.search(r"[\x00-\x20]",url)):
        fail("unapproved source URL or host")
    if len(part.path)>800 or len(part.query)>500 or "//" in part.path:
        fail("malformed approved URL path")
    return host,(part.path or "/")+("?" + part.query if part.query else "")

class PinnedConnection(HTTPSConnection):
    def __init__(self,host,peer,timeout):
        super().__init__(host,port=443,timeout=timeout,context=ssl.create_default_context())
        self.peer=peer
    def connect(self):
        self.sock=socket.create_connection((self.peer,443),self.timeout)
        self.sock=self._context.wrap_socket(self.sock,server_hostname=self.host)

def safe_resolve(host):
    info=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM,proto=socket.IPPROTO_TCP)
    addrs=sorted({x[4][0] for x in info})
    if not addrs:
        fail("public hostname unresolved")
    for a in addrs:
        if not ip_address(a).is_global:
            fail("nonpublic DNS address rejected")
    return addrs[0]

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip=0
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript","svg"):
            self.skip+=1
        if tag in ("p","h1","h2","h3","h4","li","article","section","div"):
            self.parts.append("\n")
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg") and self.skip>0:
            self.skip-=1
        if tag in ("p","h1","h2","h3","h4","li","article","section","div"):
            self.parts.append("\n")
    def handle_data(self,data):
        if not self.skip and data.strip():
            self.parts.append(data+" ")

def normalized_text(raw,content_type):
    text=raw.decode("utf-8","replace")
    if content_type.startswith("text/html"):
        parser=Text()
        parser.feed(text)
        text="".join(parser.parts)
    return re.sub(r"\s+"," ",text).strip()[:MAX_TEXT]

def fetch(url,*,timeout=12, transport=None, resolve=None):
    host,path=safe_source(url)
    if not isinstance(timeout,(float,int)) or not 0 < timeout <= 60:
        fail("invalid finite per-source deadline")
    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:
        fail("cannot replace a preexisting caller deadline")
    old_handler=signal.getsignal(signal.SIGALRM)
    def expired(_signum,_frame):
        raise TimeoutError("bounded source retrieval wall-clock deadline exceeded")
    conn=None
    signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,timeout)
    try:
        peer=(resolve or safe_resolve)(host)
        if not ip_address(peer).is_global:
            fail("peer IP is not global")
        conn=(transport or PinnedConnection)(host,peer,timeout)
        conn.request("GET",path,headers={
            "Accept":"text/html,text/plain",
            "Accept-Encoding":"identity",
            "User-Agent":"GhostMesh-ReasonPackResearch/0.1",
            "Connection":"close"
        })
        response=conn.getresponse()
        if response.status!=200:
            fail("HTTP non-success or redirect: "+str(response.status))
        mime=response.getheader("Content-Type","").split(";")[0].strip().lower()
        if mime not in ("text/html","text/plain"):
            fail("unsupported public source MIME")
        declared=response.getheader("Content-Length")
        if declared and (not declared.isdigit() or int(declared)>MAX_BODY):
            fail("oversized declared source")
        raw=response.read(MAX_BODY+1)
        if len(raw)>MAX_BODY:fail("oversized downloaded source")
        if not raw:fail("empty external source")
        return raw,mime,peer
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,old_handler)
        if conn: conn.close()

def write_private(target,bytes_):
    if target.exists() or target.is_symlink():
        fail("output exists")
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(bytes_)
        f.flush()
        os.fsync(f.fileno())

def load_catalog(path, *, private_test_override=False):
    repo=Path(__file__).resolve().parents[1]
    allowed=(repo/"editorial/research-catalogs").resolve()
    if not private_test_override and (path.resolve().parent != allowed or path.is_symlink()):
        fail("research catalog must be a repository-curated immutable source file")
    catalog=json.loads(path.read_text("utf-8"))
    if catalog.get("schema")!="ghostmesh.reasonpack.approved-research-catalog.v1" or catalog.get("operator_curated_for_private_research") is not True:
        fail("unapproved research catalog")
    entries=catalog.get("sources")
    if not isinstance(entries,list) or not 1<=len(entries)<=MAX_SOURCES:
        fail("catalog size invalid")
    used_ids=set()
    used_urls=set()
    for s in entries:
        if not isinstance(s,dict):fail("invalid catalog row")
        sid=s.get("id")
        if not isinstance(sid,str) or not ID.fullmatch(sid) or sid in used_ids:
            fail("bad or duplicate source ID")
        used_ids.add(sid)
        url=s.get("url")
        safe_source(url)
        if url in used_urls:fail("duplicate URL")
        used_urls.add(url)
        for field,limit in (("title",300),("publisher",180),("needle",1000)):
            v=s.get(field)
            if not isinstance(v,str) or not v.strip() or len(v)>limit:
                fail("invalid "+field)
        if s.get("evidence_type") not in ("primary","independent","contemporaneous","context"):
            fail("invalid source classification")
    return catalog

def collect(packet_path,catalog_path,outdir,*,fetcher=None,private_test_override=False):
    if outdir.exists() or outdir.is_symlink():
        fail("source capture output exists")
    packet=json.loads(packet_path.read_text("utf-8"))
    if packet.get("schema")!="ghostmesh.reasonpack.editorial-packet.v1":
        fail("invalid bounded ReasonPack job")
    for field in ("source_manifest_sha256","transcript_sha256"):
        if not isinstance(packet.get(field),str) or not HASH.fullmatch(packet[field]):
            fail("invalid "+field)
    catalog=load_catalog(catalog_path,private_test_override=private_test_override)
    # Exact snapshots carry the source transcript and approved source list lineage.
    captures=[]
    raw_snapshots=[]
    registry={"schema":"ghostmesh.reasonpack.evidence.v1",
              "source_manifest_sha256":packet["source_manifest_sha256"],
              "transcript_sha256":packet["transcript_sha256"],
              "sources":[]}
    for row in catalog["sources"]:
        content,mime,ip=(fetcher or fetch)(row["url"])
        page=normalized_text(content,mime)
        needle=re.sub(r"\s+"," ",row["needle"]).strip()
        match=re.search(re.escape(needle),page,re.IGNORECASE)
        if not match:
            fail("reviewed excerpt missing from independently retrieved public content: "+row["id"])
        excerpt=page[match.start():][:min(1400,len(page))]
        now=datetime.now(timezone.utc).isoformat()
        registry["sources"].append({"id":row["id"],"url":row["url"],
           "title":row["title"],"publisher":row["publisher"],
           "evidence_type":row["evidence_type"],"retrieved_at_utc":now,
           "excerpt":excerpt,"excerpt_sha256":digest(excerpt.encode())})
        raw_snapshots.append((row["id"],content,page))
        captures.append({"source_id":row["id"],"url":row["url"],"host":urlsplit(row["url"]).hostname,
                         "peer_ip":ip,"mime":mime,"retrieved_at_utc":now,"raw_sha256":digest(content),
                         "raw_bytes":len(content),"visible_text_sha256":digest(page.encode()),
                         "text_chars":len(page),"source_assertion":"not-semantically-reviewed"})
    outdir.mkdir(parents=True,mode=0o700)
    snapdir=outdir/"snapshots"
    snapdir.mkdir(mode=0o700)
    for sid,raw,visible_text in raw_snapshots:
        write_private(snapdir/(sid+".raw"),raw)
        write_private(snapdir/(sid+".text"),(visible_text+"\n").encode("utf-8"))
    registry_raw=(json.dumps(registry,indent=2,ensure_ascii=False)+"\n").encode()
    write_private(outdir/"research-evidence.json",registry_raw)
    receipt={"schema":"ghostmesh.reasonpack.public-capture.v1",
             "capture_status":"retrieved-and-excerpt-verified",
             "research_packet_sha256":digest(packet_path.read_bytes()),
             "approved_catalog_sha256":digest(catalog_path.read_bytes()),
             "evidence_register_sha256":digest(registry_raw),
             "captures":captures,"raw_snapshot_preserved":True,
             "semantic_claim_support":"NOT_ATTESTED",
             "model_invoked":False,"publication_authority":False,"email_dispatch_authority":False}
    write_private(outdir/"capture-receipt.json",(json.dumps(receipt,indent=2,sort_keys=True)+"\n").encode())
    return {"status":receipt["capture_status"],"sources":len(captures),
            "register_sha256":receipt["evidence_register_sha256"]}

def verify_capture(packet_path,catalog_path,folder,*,private_test_override=False):
    catalog=load_catalog(catalog_path,private_test_override=private_test_override)
    if not folder.is_dir() or folder.is_symlink():
        fail("missing immutable capture directory")
    receipt=json.loads((folder/"capture-receipt.json").read_text("utf-8"))
    registry_bytes=(folder/"research-evidence.json").read_bytes()
    registry=json.loads(registry_bytes)
    if receipt.get("schema")!="ghostmesh.reasonpack.public-capture.v1":
        fail("unexpected capture receipt schema")
    if receipt.get("capture_status")!="retrieved-and-excerpt-verified":
        fail("not a completed capture")
    if receipt.get("research_packet_sha256")!=digest(packet_path.read_bytes()):
        fail("source research packet changed after capture")
    if receipt.get("approved_catalog_sha256")!=digest(catalog_path.read_bytes()):
        fail("approved source catalog changed")
    if receipt.get("evidence_register_sha256")!=digest(registry_bytes):
        fail("evidence register changed after capture")
    if receipt.get("semantic_claim_support")!="NOT_ATTESTED" or receipt.get("model_invoked") is not False:
        fail("invalid claim of semantic verification or model invocation")
    if receipt.get("publication_authority") is not False or receipt.get("email_dispatch_authority") is not False:
        fail("capture must have no delivery or publication authority")
    if not isinstance(registry.get("sources"),list) or len(registry["sources"])!=len(catalog["sources"]):
        fail("captured evidence source count mismatch")
    records=receipt.get("captures")
    if not isinstance(records,list) or len(records)!=len(catalog["sources"]):
        fail("captured source inventory mismatch")
    packet=json.loads(packet_path.read_text("utf-8"))
    if registry.get("source_manifest_sha256")!=packet.get("source_manifest_sha256") or registry.get("transcript_sha256")!=packet.get("transcript_sha256"):
        fail("evidence registry not bound to exact source pack")
    snapdir=folder/"snapshots"
    if not snapdir.is_dir() or snapdir.is_symlink():
        fail("missing capture snapshot set")
    allowed=set()
    for c,source,row in zip(records,registry["sources"],catalog["sources"]):
        if c.get("source_id")!=row["id"] or c.get("url")!=row["url"] or source.get("id")!=row["id"] or source.get("url")!=row["url"]:
            fail("capture source attribution changed")
        raw_path=snapdir/(row["id"]+".raw")
        text_path=snapdir/(row["id"]+".text")
        allowed.update([raw_path.name,text_path.name])
        for path in (raw_path,text_path):
            if not path.is_file() or path.is_symlink():
                fail("missing or symlinked source evidence")
        raw=raw_path.read_bytes()
        saved_text=text_path.read_bytes()
        if len(raw)>MAX_BODY or len(raw)!=c.get("raw_bytes") or digest(raw)!=c.get("raw_sha256"):
            fail("raw source capture checksum mismatch")
        if c.get("mime") not in ("text/html","text/plain"):
            fail("unacceptable verified MIME")
        actual_text=normalized_text(raw,c["mime"])
        if saved_text != (actual_text+"\n").encode("utf-8"):
            fail("stored parsed source does not match raw evidence")
        if digest(actual_text.encode("utf-8"))!=c.get("visible_text_sha256"):
            fail("text extraction hash mismatch")
        if source.get("excerpt_sha256")!=digest(source.get("excerpt","").encode("utf-8")):
            fail("evidence excerpt hash mismatch")
        if source.get("excerpt","") not in actual_text:
            fail("evidence excerpt no longer matches raw source")
        needle=re.sub(r"\s+"," ",row["needle"]).strip()
        if not re.search(re.escape(needle),actual_text,re.IGNORECASE):
            fail("reviewed source needle absent in preserved bytes")
        if not re.match(re.escape(needle),source["excerpt"],re.IGNORECASE):
            fail("excerpt does not begin with reviewed source needle")
    actual={x.name for x in snapdir.iterdir()}
    if actual!=allowed:
        fail("unexpected or missing source snapshot members")
    return {"status":"capture-bytes-verified","sources":len(records),
            "registry_sha256":digest(registry_bytes),
            "semantic_claim_support":"NOT_ATTESTED","email_dispatch_authority":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet",type=Path,required=True)
    p.add_argument("--catalog",type=Path,required=True)
    p.add_argument("--out",type=Path)
    p.add_argument("--verify-dir",type=Path)
    args=p.parse_args()
    try:
        if bool(args.out) == bool(args.verify_dir):
            fail("select exactly one: --out or --verify-dir")
        result=(verify_capture(args.packet,args.catalog,args.verify_dir) if args.verify_dir
                else collect(args.packet,args.catalog,args.out))
        print(json.dumps(result,sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError,
            ssl.SSLError,socket.gaierror,TimeoutError) as exc:
        print("HOLD: "+str(exc),file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
