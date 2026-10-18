#!/usr/bin/env python3
"""GhostMesh future-mission and telemetry projection negative tests."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
EVENT=sha256(b"test-only provider event").hexdigest()

def cli(*a):
    return subprocess.run([sys.executable,str(ROOT/"ops/mission-receipt.py"),*map(str,a)],
                          text=True,capture_output=True)
class MissionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name)
        self.mission=self.d/"request.json"
    def create(self,kind="reasonpack"):
        return cli("create","--kind",kind,"--surface","gmail",
                   "--event-sha256",EVENT,"--out",self.mission)
    def test_reasonpack_proposal_has_no_automatic_payment_or_dispatch(self):
        a=self.create()
        self.assertEqual(a.returncode,0,a.stderr)
        record=json.loads(self.mission.read_text())
        self.assertFalse(record["customer_payment_authorized"])
        self.assertFalse(record["owner_upfront_spend_approved"])
        self.assertFalse(record["outgoing_message_authority"])
        self.assertIsNone(record["owner_spend_cap_usd"])
        self.assertEqual(record["payment_status"],"NOT_CONFIGURED")
        self.assertEqual(record["phase"],"proposed-private")
        self.assertEqual(self.mission.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.create().returncode,2)
    def test_website_preview_is_not_payment_authority(self):
        a=self.create("website_preview")
        self.assertEqual(a.returncode,0,a.stderr)
        projection=cli("project","--mission",self.mission)
        self.assertEqual(projection.returncode,0,projection.stderr)
        view=json.loads(projection.stdout)
        self.assertEqual(view["kind"],"website_preview")
        self.assertFalse(view["public_reader_published"])
        self.assertEqual(view["customer_payment_status"],"NOT_CONFIGURED")
    def test_unattested_model_and_money_are_unknown(self):
        self.assertEqual(self.create().returncode,0)
        p=cli("project","--mission",self.mission)
        self.assertEqual(p.returncode,0,p.stderr)
        d=json.loads(p.stdout)
        self.assertEqual(d["ai_invocations"],"UNKNOWN")
        self.assertIsNone(d["actual_provider_billed_cost_usd"])
        self.assertIsNone(d["customer_charge_usd"])
        self.assertIsNone(d["owner_spend_exposure_usd"])
        self.assertEqual(d["provider_delivery_acceptance"],"UNKNOWN")
        self.assertFalse(d["footer_activated"])
    def test_no_untrusted_fingerprint_accepted(self):
        p=cli("create","--kind","reasonpack","--surface","gmail",
              "--event-sha256","recipient@example.org","--out",self.mission)
        self.assertEqual(p.returncode,2)
        self.assertFalse(self.mission.exists())
    def test_projection_recomputes_mission_identity(self):
        self.assertEqual(self.create().returncode,0)
        original=json.loads(self.mission.read_text())
        for changes in ({"mission_id":"0"*64},
                        {"source_event_fingerprint":"1"*64},
                        {"surface":"owner"}):
            with self.subTest(changes=changes):
                self.mission.write_text(json.dumps(original | changes))
                result=cli("project","--mission",self.mission)
                self.assertEqual(result.returncode,2,result.stdout)
                self.assertIn("mission identity",result.stderr)
    def test_workflow_projection_is_deterministic_not_paid(self):
        self.assertEqual(self.create().returncode,0)
        wf=self.d/"workflow.json"
        wf.write_text(json.dumps({"schema":"ghostmesh.reasonpack.workflow.v1",
           "events":[
             {"to":"source-verified","at_utc":"2026-10-15T12:00:00+00:00"},
             {"to":"awaiting-research","at_utc":"2026-10-15T12:01:00+00:00"},
             {"to":"reader-private-draft","at_utc":"2026-10-15T12:15:00+00:00"}]}))
        p=cli("project","--mission",self.mission,"--workflow",wf)
        self.assertEqual(p.returncode,0,p.stderr)
        r=json.loads(p.stdout)
        self.assertEqual(len(r["stages"]),3)
        self.assertTrue(all(x["usage_tokens"]=="not_applicable" for x in r["stages"]))
        self.assertTrue(all(x["actual_provider_billed_usd"] is None for x in r["stages"]))
        self.assertEqual(r["provider_delivery_acceptance"],"UNKNOWN")
    def test_bad_workflow_stage_fails_closed(self):
        self.assertEqual(self.create().returncode,0)
        wf=self.d/"workflow.json"
        wf.write_text(json.dumps({"schema":"ghostmesh.reasonpack.workflow.v1",
             "events":[{"to":"payment-accepted","at_utc":"2026-10-15T12:00:00+00:00"}]}))
        self.assertEqual(cli("project","--mission",self.mission,"--workflow",wf).returncode,2)
if __name__=="__main__":unittest.main(verbosity=2)
