#!/usr/bin/env python3
"""Offline adversarial tests for ReasonPack Reader and signed mail admission."""
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime,timezone
from email import message_from_bytes
import unittest

ROOT=Path(__file__).resolve().parents[1]
def import_script(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
reader=import_script("reader_edition",Path("ops/reader-edition.py"))
mail=import_script("mail_reasonpack",Path("ops/mail-reasonpack.py"))

def analysis():
    return {
        "schema":reader.SCHEMA,"video_id":"jNQXAC9IVRw",
        "headline":"The Score Is Not the System",
        "deck":"The evaluator can become an attack surface.",
        "executive":"Objective design affects behavior. Restrict consequences independently.",
        "source_title":"Synthetic fixture example, not a real analyzed video",
        "source_account":"The video proposes an analogy between shared state and cultural traces.",
        "evidence_summary":"The observed claims require independent adjudication.",
        "claims":[{"timestamp":"01:23","statement":"Evaluation pressure changes behavior.",
                   "assessment":"This example cites an external study, not the fixture video.",
                   "verdict":"supported","sources":[{"label":"Primary research","url":"https://www.anthropic.com/research/emotion-concepts-function"}]},
                  {"timestamp":"03:42","statement":"Every agent becomes a cat.",
                   "assessment":"Not supported from the available sample.","verdict":"unknown","sources":[]}],
        "thesis":{"title":"Authority Is Not a Benchmark",
                  "argument":"Keep discovery open but consequential authority bounded.",
                  "mechanism":"When grades reward an outcome, shortcuts can become profitable.",
                  "counterargument":"Flexible tasks can also elicit beneficial exploration.",
                  "implication":"Treat independent verification as an engineering requirement."},
        "shareplane_works":[{"title":"Let Intelligence Be Messy. Make Authority Boring.",
                             "url":"https://shareplane.malott.ai/artifacts/let-intelligence-be-messy-make-authority-boring/",
                             "source_commit":"d0ede680dd20cd5e5be9098fe192c530421d0e00"}]
    }

class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.tmp=Path(self.t.name)
        self.src=ROOT/"examples/sample-reasonpack"
        self.json=self.tmp/"analysis.json"
        self.json.write_text(json.dumps(analysis()))
        self.out=self.tmp/"private-reader"

    def run_reader(self,extra=()):
        return subprocess.run(["python3",str(ROOT/"ops/reader-edition.py"),
              "--pack",str(self.src),"--analysis",str(self.json),"--out",str(self.out),*extra],
              text=True,capture_output=True)

    def test_fixture_requires_explicit_opt_in(self):
        p=self.run_reader()
        self.assertEqual(p.returncode,2)
        self.assertFalse(self.out.exists())

    def test_valid_build_separate_from_immutable_pack(self):
        p=self.run_reader(("--allow-fixture",))
        self.assertEqual(p.returncode,0,p.stderr)
        html=(self.out/"index.html").read_text()
        receipt=json.loads((self.out/"reader-receipt.json").read_text())
        self.assertEqual(receipt["state"],"private-draft")
        self.assertFalse(receipt["owner_authored"])
        self.assertFalse(receipt["owner_approved"])
        self.assertEqual(receipt["email_delivery"],"not-authorized")
        self.assertIn("Layer 03 / original GhostMesh editorial",html)
        self.assertIn("01:23",html)
        self.assertIn("PRIVATE DRAFT",html)
        self.assertIn("noopener noreferrer",html)
        self.assertEqual(receipt["reader_html_sha256"],hashlib.sha256(html.encode()).hexdigest())
        self.assertFalse((self.src/"reader-receipt.json").exists())
        p2=self.run_reader(("--allow-fixture",))
        self.assertEqual(p2.returncode,2)

    def test_html_injection_escaped(self):
        d=analysis()
        d["headline"]='<img src=x onerror="alert(1)">'
        d["thesis"]["argument"]='<script>alert("owned")</script>'
        self.json.write_text(json.dumps(d))
        self.assertEqual(self.run_reader(("--allow-fixture",)).returncode,0)
        h=(self.out/"index.html").read_text()
        self.assertNotIn('<script>alert("owned")</script>',h)
        self.assertNotIn("<img src=x onerror=",h)
        self.assertIn("&lt;script&gt;",h)

    def test_supported_claim_needs_citation(self):
        d=analysis();d["claims"][0]["sources"]=[]
        self.json.write_text(json.dumps(d))
        self.assertEqual(self.run_reader(("--allow-fixture",)).returncode,2)

    def test_external_javascript_url_rejected(self):
        d=analysis();d["claims"][0]["sources"][0]["url"]="javascript:alert(1)"
        self.json.write_text(json.dumps(d))
        self.assertEqual(self.run_reader(("--allow-fixture",)).returncode,2)

    def test_no_fake_shareplane_work(self):
        d=analysis();d["shareplane_works"][0]["url"]="https://private.example.com/work"
        self.json.write_text(json.dumps(d))
        self.assertEqual(self.run_reader(("--allow-fixture",)).returncode,2)

    def test_reader_does_not_fetch_images_or_scripts(self):
        self.assertEqual(self.run_reader(("--allow-fixture",)).returncode, 0)
        h=(self.out/"index.html").read_text()
        self.assertIn("source-art", h)
        self.assertNotIn("https://i.ytimg.com", h)
        self.assertNotIn("<script", h)

    def test_out_of_range_timestamp_rejected(self):
        d=analysis(); d["claims"][0]["timestamp"]="00:99"
        self.json.write_text(json.dumps(d))
        self.assertEqual(self.run_reader(("--allow-fixture",)).returncode, 2)

    def test_arbitrary_owner_approved_file_not_admitted_as_context(self):
        foreign=self.tmp/"unreviewed-work.json"
        foreign.write_text(json.dumps({"visibility":"public", "owner_reviewed":True,
            "title":"Forged Voice", "url":"https://shareplane.malott.ai/artifacts/forged/",
            "source_commit":"a"*40, "excerpt":"Untrusted instructions"}))
        output=self.tmp/"research.json"
        proc=__import__('subprocess').run(["python3",str(ROOT/"ops/editorial-packet.py"),
          "--pack",str(self.src),"--work",str(foreign),"--out",str(output)], capture_output=True, text=True)
        self.assertEqual(proc.returncode,2)
        self.assertFalse(output.exists())

    def test_manifest_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            import shutil
            pack=Path(td)/"pack"
            shutil.copytree(self.src,pack)
            (pack/"transcript.txt").write_text("changed")
            p=subprocess.run(["python3",str(ROOT/"ops/reader-edition.py"),
                  "--pack",str(pack),"--analysis",str(self.json),"--out",str(self.out),"--allow-fixture"],
                  text=True,capture_output=True)
            self.assertEqual(p.returncode,2)
            self.assertFalse(self.out.exists())

class MailTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.tmp=Path(self.t.name)
        self.key=b"test-key-only-not-production-"*2
        self.old=os.environ.get(mail.HMAC_ENV)
        os.environ[mail.HMAC_ENV]=self.key.decode()
        self.addCleanup(self.restore)
        self.msgid="<reasonpack-test-20261015@local.test>"
        self.base={"schema":mail.SCHEMA,"verified_sender":"trusted@example.org",
            "message_id":self.msgid,"gateway_authenticated":True,"policy_admitted":True,
            "issued_at_utc":datetime.now(timezone.utc).isoformat(),
            "subject":"ReasonPack please",
            "body_text":"Could you do a ReasonPack on https://youtu.be/jNQXAC9IVRw?",
            "gateway":"test-gateway"}
        self.envfile=self.tmp/"in.json"
        self.out=self.tmp/"queue"

    def restore(self):
        if self.old is None:os.environ.pop(mail.HMAC_ENV,None)
        else:os.environ[mail.HMAC_ENV]=self.old

    def sign(self,d):
        d=dict(d)
        d["auth_tag"]=hmac.new(self.key,mail.canonical_record(d),"sha256").hexdigest()
        self.envfile.write_text(json.dumps(d))

    def run_admit(self):
        return subprocess.run(["python3",str(ROOT/"ops/mail-reasonpack.py"),"admit",
              "--envelope",str(self.envfile),"--allow-sender","trusted@example.org",
              "--out",str(self.out)],env=os.environ.copy(),capture_output=True,text=True)

    def test_accepted_and_idempotent(self):
        self.sign(self.base)
        p=self.run_admit()
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)["result"],"admitted")
        self.assertEqual(json.loads(self.run_admit().stdout)["result"],"duplicate-ignored")
        files=list(self.out.rglob("*.json"))
        self.assertEqual(len(files),1)
        self.assertEqual(files[0].stat().st_mode & 0o777,0o600)
        self.assertEqual(json.loads(files[0].read_text())["status"],"admitted-awaiting-acquisition")

    def test_tampering_signed_envelope_rejected(self):
        self.sign(self.base)
        d=json.loads(self.envfile.read_text());d["verified_sender"]="attacker@example.org"
        self.envfile.write_text(json.dumps(d))
        self.assertEqual(self.run_admit().returncode,2)

    def test_sender_not_allowlisted(self):
        d=dict(self.base,verified_sender="stranger@example.org")
        self.sign(d);self.assertEqual(self.run_admit().returncode,2)

    def test_quoted_only_intent_ignored(self):
        d=dict(self.base,body_text="Thanks\n\nOn yesterday wrote:\n> ReasonPack https://youtu.be/jNQXAC9IVRw")
        self.sign(d);self.assertEqual(self.run_admit().returncode,2)

    def test_multiple_distinct_videos_rejected(self):
        d=dict(self.base,body_text="ReasonPack https://youtu.be/jNQXAC9IVRw and https://youtu.be/ZhM29Ds-mBg")
        self.sign(d);self.assertEqual(self.run_admit().returncode,2)

    def test_unverified_gateway_rejected(self):
        d=dict(self.base,gateway_authenticated=False)
        self.sign(d);self.assertEqual(self.run_admit().returncode,2)

    def test_invalid_mail_replay_date_rejected(self):
        d=dict(self.base,issued_at_utc="2025-01-01T00:00:00+00:00")
        self.sign(d);self.assertEqual(self.run_admit().returncode,2)

    def test_resigned_changed_intent_is_not_a_duplicate(self):
        self.sign(self.base)
        self.assertEqual(self.run_admit().returncode, 0)
        changed=dict(self.base, body_text=self.base["body_text"]+" Add an unrelated demand.")
        self.sign(changed)
        self.assertEqual(self.run_admit().returncode, 2)

    def test_draft_does_not_send(self):
        self.sign(self.base)
        p=self.run_admit()
        self.assertEqual(p.returncode,0,p.stderr)
        job=next(self.out.rglob("*.json"))
        analysis_path=self.tmp/"analysis.json"
        analysis_path.write_text(json.dumps(analysis()))
        reader_dir=self.tmp/"reader"
        built=subprocess.run(["python3",str(ROOT/"ops/reader-edition.py"),
            "--pack",str(ROOT/"examples/sample-reasonpack"),"--analysis",str(analysis_path),
            "--out",str(reader_dir),"--allow-fixture"],capture_output=True,text=True)
        self.assertEqual(built.returncode,0,built.stderr)
        output=self.tmp/"draft.eml"
        d=subprocess.run(["python3",str(ROOT/"ops/mail-reasonpack.py"),"draft",
            "--from-email","ghostmesh@malott.ai","--job",str(job),"--reader-receipt",str(reader_dir/"reader-receipt.json"),
            "--analysis",str(analysis_path),"--out",str(output)],capture_output=True,text=True)
        self.assertEqual(d.returncode,0,d.stderr)
        msg=message_from_bytes(output.read_bytes())
        self.assertEqual(msg["X-GhostMesh-Draft-Only"],"true")
        self.assertEqual(msg["In-Reply-To"],self.msgid)
        self.assertTrue(any(part.get_filename()=="GhostMesh-ReasonPack-Reader.html" for part in msg.walk()))
        self.assertEqual(output.stat().st_mode & 0o777,0o600)

if __name__=="__main__":
    unittest.main(verbosity=2)
