#!/usr/bin/env python3
"""Network-free adversarial tests for allowlisted DNS-pinned HTTPS capture."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import importlib.util
import json
import os
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("capture",ROOT/"ops/public-source-capture.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SOURCE="https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/"
PAGE=b'<html><head><title>Research</title><style>secret payload</style></head><body><h1>Incident Report</h1><p>Roughly 1200 agents communicated outside of their evaluation sandbox.</p><script>bad()</script></body></html>'

class Response:
    status=200
    def __init__(self,raw=PAGE,status=200,mime="text/html",size=None):
        self.raw=raw
        self.status=status
        self.mime=mime
        self.size=size
    def getheader(self,key,default=None):
        if key=="Content-Type":return self.mime
        if key=="Content-Length":return str(self.size) if self.size is not None else str(len(self.raw))
        return default
    def read(self,n):return self.raw[:n]

class Connection:
    responses=[]
    requests=[]
    addresses=[]
    def __init__(self,host,peer,timeout):
        self.addresses.append((host,peer,timeout))
    def request(self,method,path,headers):
        self.requests.append((method,path,headers))
    def getresponse(self):
        return self.responses.pop(0)
    def close(self):pass

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.packet=self.root/"packet.json"
        self.packet.write_text(json.dumps({
            "schema":"ghostmesh.reasonpack.editorial-packet.v1",
            "source_manifest_sha256":"a"*64,
            "transcript_sha256":"b"*64
        }))
        self.catalog=self.root/"catalog.json"
        self.source={"id":"src-metr2026","url":SOURCE,"title":"Independent incident review",
             "publisher":"METR","needle":"Roughly 1200 agents communicated",
             "evidence_type":"independent"}
        self.save_catalog()
        self.out=self.root/"captured"
        Connection.responses=[]
        Connection.requests=[]
        Connection.addresses=[]
    def save_catalog(self):
        self.catalog.write_text(json.dumps({"schema":"ghostmesh.reasonpack.approved-research-catalog.v1",
             "operator_curated_for_private_research":True,"sources":[self.source]}))
    def test_html_content_and_explicit_excerpt_match(self):
        def fake_fetch(url):
            return PAGE,"text/html","8.8.8.8"
        result=mod.collect(self.packet,self.catalog,self.out,private_test_override=True,fetcher=fake_fetch)
        self.assertEqual(result["sources"],1)
        proof=mod.verify_capture(self.packet,self.catalog,self.out,private_test_override=True)
        self.assertEqual(proof["status"],"capture-bytes-verified")
        reg=json.loads((self.out/"research-evidence.json").read_text())
        self.assertEqual(reg["sources"][0]["url"],SOURCE)
        self.assertIn("Roughly 1200 agents communicated",reg["sources"][0]["excerpt"])
        self.assertEqual(reg["sources"][0]["excerpt_sha256"],
                         sha256(reg["sources"][0]["excerpt"].encode()).hexdigest())
        self.assertEqual((self.out/"snapshots/src-metr2026.raw").read_bytes(),PAGE)
        self.assertIn("Roughly 1200 agents communicated", (self.out/"snapshots/src-metr2026.text").read_text())
        rec=json.loads((self.out/"capture-receipt.json").read_text())
        self.assertFalse(rec["publication_authority"])
        self.assertFalse(rec["email_dispatch_authority"])
        self.assertEqual(rec["semantic_claim_support"],"NOT_ATTESTED")
        self.assertEqual((self.out/"capture-receipt.json").stat().st_mode & 0o777,0o600)
        with self.assertRaises(ValueError):mod.collect(self.packet,self.catalog,self.out,private_test_override=True,fetcher=fake_fetch)
    def test_unapproved_hostname_rejected(self):
        for url in ("http://metr.org/blog","https://127.0.0.1/",
                    "https://metadata.google.internal/","https://evil.metr.org/",
                    "https://metr.org@127.0.0.1/","https://metr.org:444/x",
                    "https://metr.org/a#fragment"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                mod.safe_source(url)
    def test_private_dns_answer_rejected(self):
        with self.assertRaises(ValueError):
            mod.fetch(SOURCE,resolve=lambda _: "127.0.0.1",transport=Connection)
        self.assertEqual(Connection.requests,[])
    def test_request_has_no_ambient_cookies_or_redirect_following(self):
        Connection.responses=[Response()]
        raw,mime,peer=mod.fetch(SOURCE,transport=Connection,resolve=lambda _:"8.8.8.8")
        self.assertEqual(raw,PAGE)
        self.assertEqual(peer,"8.8.8.8")
        self.assertEqual(Connection.addresses[0][1],"8.8.8.8")
        method,path,headers=Connection.requests[0]
        self.assertEqual(method,"GET")
        self.assertTrue(path.startswith("/blog/"))
        self.assertNotIn("Cookie",headers)
        self.assertNotIn("Authorization",headers)
    def test_redirect_fails_closed(self):
        Connection.responses=[Response(status=302)]
        with self.assertRaisesRegex(ValueError,"redirect"):
            mod.fetch(SOURCE,transport=Connection,resolve=lambda _:"8.8.8.8")
    def test_non_html_or_oversize_fails(self):
        for response in (Response(mime="application/pdf"),Response(size=mod.MAX_BODY+1),
                         Response(raw=b"x"*(mod.MAX_BODY+1))):
            Connection.responses=[response]
            with self.assertRaises(ValueError):
                mod.fetch(SOURCE,transport=Connection,resolve=lambda _:"8.8.8.8")
    def test_excerpt_must_occur_in_fetched_bytes(self):
        self.source["needle"]="The researcher personally inspected the internet"
        self.save_catalog()
        with self.assertRaisesRegex(ValueError,"excerpt missing"):
            mod.collect(self.packet,self.catalog,self.out,private_test_override=True,fetcher=lambda _: (PAGE,"text/html","8.8.8.8"))
        self.assertFalse(self.out.exists())
    def test_mutated_raw_source_is_rejected_on_readback(self):
        mod.collect(self.packet,self.catalog,self.out,private_test_override=True,
                    fetcher=lambda _: (PAGE,"text/html","8.8.8.8"))
        with (self.out/"snapshots/src-metr2026.raw").open("ab") as f:f.write(b"extra")
        with self.assertRaisesRegex(ValueError,"checksum"):
            mod.verify_capture(self.packet,self.catalog,self.out,private_test_override=True)

    def test_mutated_registry_fails_exact_capture_binding(self):
        mod.collect(self.packet,self.catalog,self.out,private_test_override=True,
                    fetcher=lambda _: (PAGE,"text/html","8.8.8.8"))
        with (self.out/"research-evidence.json").open("ab") as f:f.write(b" ")
        with self.assertRaisesRegex(ValueError,"evidence register changed"):
            mod.verify_capture(self.packet,self.catalog,self.out,private_test_override=True)

    def test_arbitrary_runtime_catalog_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"repository-curated"):
            mod.load_catalog(self.catalog)

    def test_unreviewed_source_manifest_rejected(self):
        d=json.loads(self.catalog.read_text())
        d["operator_curated_for_private_research"]=False
        self.catalog.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,"unapproved"):
            mod.collect(self.packet,self.catalog,self.out,private_test_override=True,fetcher=lambda _: (PAGE,"text/html","8.8.8.8"))
    def test_source_bound_to_exact_video_pack(self):
        registry=mod.collect(self.packet,self.catalog,self.out,private_test_override=True,fetcher=lambda _: (PAGE,"text/html","8.8.8.8"))
        p=json.loads((self.out/"research-evidence.json").read_text())
        self.assertEqual(p["source_manifest_sha256"],"a"*64)
        self.assertEqual(p["transcript_sha256"],"b"*64)

if __name__=="__main__":unittest.main(verbosity=2)
