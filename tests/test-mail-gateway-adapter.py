#!/usr/bin/env python3
"""Offline contract checks for the in-process authenticated mail adapter."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("gateway",ROOT/"ops/mail-gateway-adapter.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.item={
            "gmail_id":"abcdef1234567890",
            "gmail_thread_id":"abcdef1234567890",
            "sender":"owner-test@example.org",
            "message_id_header":"<source-123@example.org>",
            "subject":"Please analyze this",
            "body":"Please run a ReasonPack https://youtu.be/jNQXAC9IVRw",
        }
        self.key=b"synthetic-signing-key-"*3
    def envelope(self, **kw):
        return mod.normalize_verified_item(self.item, admitted=True,owner_only=True,
              owner_sender="owner-test@example.org",key=self.key, **kw)
    def test_validated_source_preserves_gmail_thread(self):
        e=self.envelope()
        self.assertTrue(mod.validate_handoff_contract(e,sender=self.item["sender"],
                    gmail_id=self.item["gmail_id"],gmail_thread_id=self.item["gmail_thread_id"]))
        self.assertIn("auth_tag",e)
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"envelope.json";source.write_text(json.dumps(e))
            env=os.environ.copy();env["REASONPACK_MAIL_INGEST_KEY"]=self.key.decode()
            r=subprocess.run([sys.executable,str(ROOT/"ops/mail-reasonpack.py"),"admit",
                "--envelope",str(source),"--allow-sender",self.item["sender"],
                "--out",str(Path(td)/"queue")],env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            receipt=next((Path(td)/"queue").rglob("*.json"))
            record=json.loads(receipt.read_text())
            self.assertEqual(record["gmail_thread_id"],self.item["gmail_thread_id"])
            self.assertEqual(record["gmail_id"],self.item["gmail_id"])

    def test_authenticated_flag_is_not_optional(self):
        with self.assertRaises(mod.AdapterDenied):
            mod.normalize_verified_item(self.item,admitted=False,owner_only=True,
                owner_sender=self.item["sender"],key=self.key)

    def test_owner_pilot_blocks_other_senders(self):
        self.item["sender"]="other@example.org"
        with self.assertRaises(mod.AdapterDenied):
            self.envelope()

    def test_bad_thread_is_rejected(self):
        self.item["gmail_thread_id"]="cross-thread\ninjection"
        with self.assertRaises(mod.AdapterDenied):
            self.envelope()

    def test_tampering_with_signed_sender_is_detected(self):
        e=self.envelope()
        e["verified_sender"]="other@example.org"
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"e.json";source.write_text(json.dumps(e))
            env=os.environ.copy();env["REASONPACK_MAIL_INGEST_KEY"]=self.key.decode()
            r=subprocess.run([sys.executable,str(ROOT/"ops/mail-reasonpack.py"),"admit",
                "--envelope",str(source),"--allow-sender","other@example.org",
                "--out",str(Path(td)/"queue")],env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,2)

    def test_missing_message_id_holds_not_rethreads(self):
        self.item["message_id_header"]=None
        with self.assertRaises(mod.AdapterDenied):
            self.envelope()

if __name__=="__main__":
    unittest.main(verbosity=2)
