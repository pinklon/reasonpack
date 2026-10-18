#!/usr/bin/env python3
"""All-segment synthesis coverage, replay and tamper regression fixtures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load():
    spec=importlib.util.spec_from_file_location("longform_synth",ROOT/"ops/longform-synthesis.py")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
S=load()

def cmd(*a):
    return subprocess.run([sys.executable,str(ROOT/"ops/longform-synthesis.py"),*map(str,a)],
                         capture_output=True,text=True)

class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.comp=self.root/"composition"
        self.comp.mkdir()
        for sub in ("segment-prompts","segment-schemas"):
            (self.comp/sub).mkdir()
        self.results=self.root/"candidates"
        self.results.mkdir()
        self.synth=self.root/"synthesis"
        self.n=11
        import hashlib
        h=lambda v:hashlib.sha256(v).hexdigest()
        items=[]
        for i in range(self.n):
            ident=f"segment-{i:06d}"
            sh=h(f"content-{i}".encode())
            p=h(f"prompt-{i}".encode())
            sj=h(f"schema-{i}".encode())
            (self.comp/"segment-prompts"/(ident+".json")).write_bytes(f"prompt-{i}".encode())
            (self.comp/"segment-schemas"/(ident+".schema.json")).write_bytes(f"schema-{i}".encode())
            row={"index":i,"path":ident+".json","segment_sha256":sh,
                 "prompt_sha256":p,"schema_path":ident+".schema.json","schema_sha256":sj}
            items.append(row)
            out={"schema":"ghostmesh.reasonpack.segment-candidate.v1",
                 "segment_index":i,"segment_sha256":sh,"prompt_sha256":p,
                 "observations":[f"Observed distinct segment {i}"],
                 "source_truth_attested":False,"final_answer_authorized":False}
            (self.results/(ident+".json")).write_text(json.dumps(out))
        self.compreceipt={"schema":"ghostmesh.reasonpack.composition.v1",
                  "transcript_mode":"segmented","source_video_id":"ZhM29Ds-mBg",
                  "research_packet_sha256":"a"*64,
                  "evidence_registry_sha256":"b"*64,
                  "segment_prompt_receipts":items}
        prompt={"rules":["Summarize the whole video without operational authority"],
                 "bounded_evidence":{"untrusted_video_transcript":"","research_evidence":[]}}
        ptext=json.dumps(prompt).encode()
        schema=json.dumps({"type":"object","properties":{}}).encode()
        (self.comp/"model-prompt.json").write_bytes(ptext)
        (self.comp/"analysis-schema.json").write_bytes(schema)
        self.compreceipt["model_prompt_sha256"]=__import__("hashlib").sha256(ptext).hexdigest()
        self.compreceipt["model_schema_sha256"]=__import__("hashlib").sha256(schema).hexdigest()
        (self.comp/"composition-receipt.json").write_text(json.dumps(self.compreceipt))
    def call(self,name,*args):
        return cmd(name,"--composition",self.comp,"--results",self.results,
                   "--synthesis",self.synth,*args)
    def init(self):
        p=self.call("init")
        self.assertEqual(p.returncode,0,p.stderr)
        return json.loads(p.stdout)
    def finish(self):
        self.init()
        plan=json.loads((self.synth/"plan.json").read_text())
        for level in plan["levels"]:
            for n in level:
                node=n["id"]
                p=self.call("prepare","--node",node)
                self.assertEqual(p.returncode,0,p.stderr)
                source=json.loads((self.synth/"prompts"/(node+".json")).read_text())
                observation={"schema":"ghostmesh.reasonpack.synthesis-node.v1",
                     "node_id":node,
                     "node_prompt_sha256":json.loads(p.stdout)["prompt_sha256"],
                     "child_sha256":[v["sha256"] for v in source["children"]],
                     "observations":["Provisional combined observations of "+node],
                     "semantic_truth_attested":False,"publication_authority":False}
                path=self.root/(node+"-result.json")
                path.write_text(json.dumps(observation))
                result=self.call("stage","--node",node,"--candidate",path)
                self.assertEqual(result.returncode,0,result.stderr)
        return plan
    def test_all_segments_reconstruct_recursive_coverage(self):
        plan=self.finish()
        self.assertGreater(len(plan["levels"]),3)
        sealed=self.call("seal")
        self.assertEqual(sealed.returncode,0,sealed.stderr)
        r=json.loads((self.synth/"coverage-receipt.json").read_text())
        self.assertEqual(r["segments_covered"],self.n)
        self.assertEqual(r["nodes_verified"],sum(len(x) for x in plan["levels"]))
        self.assertEqual(r["semantic_review"],"NOT_ATTESTED")
        final_prompt=(self.synth/"whole-video-model-input.json")
        self.assertTrue(final_prompt.is_file())
        self.assertEqual(r["whole_video_prompt_sha256"],__import__('hashlib').sha256(final_prompt.read_bytes()).hexdigest())
        self.assertEqual(json.loads(final_prompt.read_text())["bounded_evidence"]["whole_video_synthesis"]["segment_count"],self.n)
        self.assertFalse(r["email_dispatch_authority"])
        self.assertEqual(self.call("verify").returncode,0)
        self.assertEqual(json.loads(self.call("seal").stdout)["coverage_sha256"],
                         json.loads(sealed.stdout)["coverage_sha256"])
    def test_missing_leaf_holds(self):
        (self.results/"segment-000007.json").unlink()
        p=self.call("init")
        self.assertEqual(p.returncode,2)
        self.assertIn("missing",p.stderr)
    def test_unfinished_synthesis_cannot_seal(self):
        self.init()
        p=self.call("seal")
        self.assertEqual(p.returncode,2)
        self.assertFalse((self.synth/"coverage-receipt.json").exists())
    def test_out_of_order_node_holds(self):
        self.init()
        plan=json.loads((self.synth/"plan.json").read_text())
        top=plan["levels"][-1][0]["id"]
        self.assertEqual(self.call("prepare","--node",top).returncode,2)
    def test_tampered_leaf_holds(self):
        self.init()
        f=self.results/"segment-000003.json"
        f.write_text(f.read_text()+" ")
        self.assertEqual(self.call("prepare","--node","level-001-node-000001").returncode,2)
    def test_modified_node_is_rejected_after_sealing(self):
        self.finish()
        self.assertEqual(self.call("seal").returncode,0)
        node=next((self.synth/"candidates").glob("*.json"))
        node.write_bytes(node.read_bytes()+b" ")
        self.assertEqual(self.call("verify").returncode,2)
    def test_invalid_operational_authority_rejected(self):
        self.init()
        node="level-001-node-000000"
        p=json.loads(self.call("prepare","--node",node).stdout)
        source=json.loads((self.synth/"prompts"/(node+".json")).read_text())
        candidate={"schema":"ghostmesh.reasonpack.synthesis-node.v1","node_id":node,
                  "node_prompt_sha256":p["prompt_sha256"],
                  "child_sha256":[v["sha256"] for v in source["children"]],
                  "observations":["Model thinks it owns deployment"],
                  "semantic_truth_attested":False,"publication_authority":True}
        f=self.root/"bad.json";f.write_text(json.dumps(candidate))
        self.assertEqual(self.call("stage","--node",node,"--candidate",f).returncode,2)
        self.assertFalse((self.synth/"candidates"/(node+".json")).exists())
    def test_missing_untrusted_node_record_holds(self):
        self.finish()
        node=next((self.synth/"candidates").glob("*.json"))
        node.unlink()
        self.assertEqual(self.call("seal").returncode,2)
    def test_candidate_replay_is_idempotent_conflict_rejected(self):
        self.init()
        node="level-001-node-000000"
        m=json.loads(self.call("prepare","--node",node).stdout)
        source=json.loads((self.synth/"prompts"/(node+".json")).read_text())
        candidate={"schema":"ghostmesh.reasonpack.synthesis-node.v1","node_id":node,
                  "node_prompt_sha256":m["prompt_sha256"],
                  "child_sha256":[v["sha256"] for v in source["children"]],
                  "observations":["Observation A"],"semantic_truth_attested":False,
                  "publication_authority":False}
        f=self.root/"good.json";f.write_text(json.dumps(candidate))
        self.assertEqual(self.call("stage","--node",node,"--candidate",f).returncode,0)
        self.assertEqual(self.call("stage","--node",node,"--candidate",f).returncode,0)
        candidate["observations"]=["Different"]
        f.write_text(json.dumps(candidate))
        self.assertEqual(self.call("stage","--node",node,"--candidate",f).returncode,2)
    def test_whole_video_validation_requires_exact_sealed_coverage(self):
        # A fabricated whole-video claim cannot skip the all-segment map-reduce tree.
        import hashlib
        from datetime import datetime,timezone
        packet=self.root/"research-input.json"
        registry=self.root/"registry.json"
        source_excerpt="Synthetic fixture source excerpt"
        research={"schema":"ghostmesh.reasonpack.editorial-packet.v1",
            "source_url":"https://www.youtube.com/watch?v=ZhM29Ds-mBg",
            "source_manifest_sha256":"c"*64,"transcript_sha256":"d"*64,
            "transcript_mode":"segmented","segment_count":self.n,
            "public_owner_reviewed_thesis_context":[]}
        packet.write_text(json.dumps(research))
        evidence={"schema":"ghostmesh.reasonpack.evidence.v1",
            "source_manifest_sha256":"c"*64,"transcript_sha256":"d"*64,
            "sources":[{"id":"src-test0001","url":"https://metr.org/blog/test",
                "title":"Synthetic source","publisher":"Test fixture",
                "excerpt":source_excerpt,
                "excerpt_sha256":hashlib.sha256(source_excerpt.encode()).hexdigest(),
                "evidence_type":"context",
                "retrieved_at_utc":datetime.now(timezone.utc).isoformat()}]}
        registry.write_text(json.dumps(evidence))
        self.compreceipt["research_packet_sha256"]=hashlib.sha256(packet.read_bytes()).hexdigest()
        self.compreceipt["evidence_registry_sha256"]=hashlib.sha256(registry.read_bytes()).hexdigest()
        prompt={"rules":["Summarize the whole video without operational authority"],
                 "bounded_evidence":{"untrusted_video_transcript":"","research_evidence":[]}}
        ptext=json.dumps(prompt).encode()
        schema=json.dumps({"type":"object","properties":{}}).encode()
        (self.comp/"model-prompt.json").write_bytes(ptext)
        (self.comp/"analysis-schema.json").write_bytes(schema)
        self.compreceipt["model_prompt_sha256"]=__import__("hashlib").sha256(ptext).hexdigest()
        self.compreceipt["model_schema_sha256"]=__import__("hashlib").sha256(schema).hexdigest()
        (self.comp/"composition-receipt.json").write_text(json.dumps(self.compreceipt))
        plan=self.finish()
        self.assertEqual(self.call("seal").returncode,0)
        final=self.root/"candidate.json"
        data=json.loads((ROOT/"examples/reader-synthetic-analysis.json").read_text())
        data["video_id"]="ZhM29Ds-mBg"
        final.write_text(json.dumps(data))
        base=["validate","--packet",packet,"--registry",registry,
              "--candidate",final,"--out",self.root/"validated.json"]
        incomplete=subprocess.run([sys.executable,str(ROOT/"ops/research-composer.py"),*map(str,base)],
                text=True,capture_output=True)
        self.assertEqual(incomplete.returncode,2)
        full=subprocess.run([sys.executable,str(ROOT/"ops/research-composer.py"),*map(str,base),
                "--synthesis",str(self.synth),"--composition",str(self.comp),
                "--segment-results",str(self.results)],text=True,capture_output=True)
        self.assertEqual(full.returncode,2)
        self.assertIn("sealed whole-video prompt",full.stderr)
        data["whole_video_prompt_sha256"]="0"*64
        final.write_text(json.dumps(data))
        wrong=subprocess.run([sys.executable,str(ROOT/"ops/research-composer.py"),*map(str,base),
                 "--synthesis",str(self.synth),"--composition",str(self.comp),
                 "--segment-results",str(self.results)],text=True,capture_output=True)
        self.assertEqual(wrong.returncode,2)
        self.assertIn("sealed whole-video prompt",wrong.stderr)
        data["whole_video_prompt_sha256"]=hashlib.sha256(
            (self.synth/"whole-video-model-input.json").read_bytes()).hexdigest()
        final.write_text(json.dumps(data))
        full=subprocess.run([sys.executable,str(ROOT/"ops/research-composer.py"),*map(str,base),
                 "--synthesis",str(self.synth),"--composition",str(self.comp),
                 "--segment-results",str(self.results)],text=True,capture_output=True)
        self.assertEqual(full.returncode,0,full.stderr)
        receipt=json.loads((self.root/"validated.json").read_text())
        self.assertEqual(receipt["all_segment_coverage_status"],"complete-unreviewed")
        self.assertEqual(receipt["semantic_review"],"NOT_ATTESTED")
        self.assertFalse(receipt["email_dispatch_authority"])
        self.assertEqual(receipt["all_segment_coverage_sha256"],
            hashlib.sha256((self.synth/"coverage-receipt.json").read_bytes()).hexdigest())

    def test_segmented_analysis_schema_requires_prompt_identity(self):
        spec=importlib.util.spec_from_file_location(
            "research_composer_schema_under_test",ROOT/"ops/research-composer.py")
        composer=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(composer)
        inline=composer.schema()
        segmented=composer.schema(segmented=True)
        self.assertNotIn("whole_video_prompt_sha256",inline["properties"])
        self.assertIn("whole_video_prompt_sha256",segmented["required"])
        self.assertEqual(segmented["properties"]["whole_video_prompt_sha256"]["pattern"],
                         "^[0-9a-f]{64}$")

    def test_valid_large_unicode_segment_observations_fit_prompt(self):
        for i in (0,1):
            path=self.results/f"segment-{i:06d}.json"
            candidate=json.loads(path.read_text())
            candidate["observations"]=["💠"*1000 for _ in range(12)]
            path.write_text(json.dumps(candidate))
        self.init()
        ready=self.call("prepare","--node","level-001-node-000000")
        self.assertEqual(ready.returncode,0,ready.stderr)
        prompt=self.synth/"prompts/level-001-node-000000.json"
        self.assertLess(prompt.stat().st_size,180_000)
        source=json.loads(prompt.read_text("utf-8"))
        self.assertEqual(source["children"][0]["observations"][0],"💠"*1000)
        self.assertEqual(source["children"][1]["observations"][0],"💠"*1000)

    def test_prompts_bound_to_original_source_identity(self):
        self.init()
        p=self.call("prepare","--node","level-001-node-000000")
        self.assertEqual(p.returncode,0,p.stderr)
        doc=json.loads((self.synth/"prompts/level-001-node-000000.json").read_text())
        self.assertEqual(doc["source_video_id"],"ZhM29Ds-mBg")
        self.assertEqual(doc["segment_count"],self.n)
        self.assertEqual(doc["evidence_registry_sha256"],"b"*64)

if __name__=="__main__":unittest.main(verbosity=2)
