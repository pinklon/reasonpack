#!/usr/bin/env python3
"""Offline long-form segmented transcript and bounded composition tests."""
from __future__ import annotations
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timedelta

ROOT=Path(__file__).resolve().parents[1]
VIDEO="jNQXAC9IVRw"
def sha(raw):return sha256(raw).hexdigest()
def run(name,*flags):
    return subprocess.run([sys.executable,str(ROOT/"ops"/name),*map(str,flags)],
           capture_output=True,text=True)

def make_pack(folder,minutes=180,oversize_line=False):
    shutil.copytree(ROOT/"examples/sample-reasonpack",folder)
    source=json.loads((folder/"source.json").read_text())
    source.update(id=VIDEO,webpage_url="https://www.youtube.com/watch?v="+VIDEO)
    (folder/"source.json").write_text(json.dumps(source))
    lines=[]
    # Synthetic transcript timing, NOT evidence that the fixture media is 3 hours long.
    for idx in range(minutes*6+1):
        seconds=idx*10
        mm,ss=divmod(seconds,60);hr,mm=divmod(mm,60)
        suffix=("a very lengthy synthetic untrusted statement with context " * 5)
        lines.append(f"[{hr:02d}:{mm:02d}:{ss:02d}] synthetic utterance {idx}: {suffix}\n")
    if oversize_line:
        lines.append("[03:01:00] "+"💠".join(["synthetic"]*5000)+"\n")
    raw="".join(lines).encode()
    (folder/"transcript.txt").write_bytes(raw)
    m=json.loads((folder/"manifest.json").read_text())
    m["sourceUrl"]="https://www.youtube.com/watch?v="+VIDEO
    m.pop("fixture",None)
    for member in m["members"]:
        f=folder/member["path"]
        member["bytes"]=f.stat().st_size
        member["sha256"]=sha(f.read_bytes())
    (folder/"manifest.json").write_text(json.dumps(m,indent=2)+"\n")
    members=[x["path"] for x in m["members"]]+["manifest.json"]
    (folder/"SHA256SUMS.txt").write_text("".join(sha((folder/n).read_bytes())+"  "+n+"\n" for n in members))
    return raw

class LongFormTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.t=Path(self.temp.name)
        self.pack=self.t/"source"
        self.raw=make_pack(self.pack)
        self.parts=self.t/"parts"

    def build(self,target=20000):
        return run("longform-segments.py","build","--pack",self.pack,
                   "--out",self.parts,"--target-bytes",target)

    def test_three_hour_transcript_is_not_rejected(self):
        self.assertGreater(len(self.raw),140_000)
        p=self.build()
        self.assertEqual(p.returncode,0,p.stderr)
        status=json.loads(p.stdout)
        self.assertGreater(status["count"],10)
        self.assertEqual(status["transcript_sha256"],sha(self.raw))
        m=json.loads((self.parts/"segments-manifest.json").read_text())
        self.assertIsNone(m["video_duration_limit"])
        self.assertEqual(sum(x["bytes"] for x in m["segments"]),len(self.raw))
        v=run("longform-segments.py","verify","--transcript",self.pack/"transcript.txt",
              "--segments",self.parts)
        self.assertEqual(v.returncode,0,v.stderr)

    def test_longest_line_split_is_utf8_safe(self):
        self.t.joinpath("source").rename(self.t/"unused")
        self.pack=self.t/"source"
        self.raw=make_pack(self.pack,oversize_line=True)
        p=self.build(16000)
        self.assertEqual(p.returncode,0,p.stderr)
        for f in (self.parts/"segments").glob("*.txt"):
            f.read_text("utf-8")
            self.assertLessEqual(f.stat().st_size,16000)
        self.assertEqual(run("longform-segments.py","verify","--transcript",
                             self.pack/"transcript.txt","--segments",self.parts).returncode,0)

    def test_edited_segment_is_rejected(self):
        self.assertEqual(self.build().returncode,0)
        p=self.parts/"segments"/"segment-000000.txt"
        p.write_bytes(p.read_bytes()+b"tamper")
        x=run("longform-segments.py","verify","--transcript",
            self.pack/"transcript.txt","--segments",self.parts)
        self.assertEqual(x.returncode,2)

    def test_removed_segment_is_rejected(self):
        self.assertEqual(self.build().returncode,0)
        next((self.parts/"segments").glob("*.txt")).unlink()
        self.assertEqual(run("longform-segments.py","verify","--transcript",
                    self.pack/"transcript.txt","--segments",self.parts).returncode,2)

    def test_editorial_and_model_inputs_are_per_segment(self):
        self.assertEqual(self.build().returncode,0)
        packet=self.t/"packet.json"
        x=run("editorial-packet.py","--pack",self.pack,"--segments",self.parts,"--out",packet)
        self.assertEqual(x.returncode,0,x.stderr)
        data=json.loads(packet.read_text())
        self.assertEqual(data["transcript_mode"],"segmented")
        self.assertEqual(data["untrusted_transcript"],"")
        self.assertEqual(data["transcript_sha256"],sha(self.raw))
        index=json.loads((self.parts/"segments-manifest.json").read_text())
        self.assertEqual(data["segment_count"],index["segment_count"])
        excerpt="Synthetic independent evidence placeholder. This is not verified research."
        source={
          "id":"src-test001","url":"https://metr.org/blog/test-source",
          "title":"Synthetic", "publisher":"Fixture",
          "evidence_type":"context","retrieved_at_utc":datetime.now().astimezone().isoformat(),
          "excerpt":excerpt,"excerpt_sha256":sha(excerpt.encode())
        }
        reg=self.t/"registry.json"
        reg.write_text(json.dumps({"schema":"ghostmesh.reasonpack.evidence.v1",
         "source_manifest_sha256":data["source_manifest_sha256"],
         "transcript_sha256":data["transcript_sha256"],"sources":[source]}))
        # UTC time is only metadata, not an authority claim.
        source["retrieved_at_utc"]="2026-10-15T00:00:00+00:00"
        reg.write_text(json.dumps({"schema":"ghostmesh.reasonpack.evidence.v1",
         "source_manifest_sha256":data["source_manifest_sha256"],
         "transcript_sha256":data["transcript_sha256"],"sources":[source]}))
        output=self.t/"composition"
        x=run("research-composer.py","prepare","--packet",packet,"--registry",reg,
              "--segments",self.parts,"--out",output)
        self.assertEqual(x.returncode,0,x.stderr)
        receipt=json.loads((output/"composition-receipt.json").read_text())
        self.assertEqual(receipt["transcript_mode"],"segmented")
        self.assertEqual(len(receipt["segment_prompt_receipts"]),index["segment_count"])
        for part in receipt["segment_prompt_receipts"]:
            path=output/"segment-prompts"/part["path"]
            payload=json.loads(path.read_text())
            self.assertEqual(payload["bounded_evidence"]["segment_identity"]["index"],part["index"])
            self.assertLess(path.stat().st_size,180_000)
            self.assertEqual(sha(path.read_bytes()),part["prompt_sha256"])
        checkpoint=self.t/"staged-segment-candidates"
        status=run("segment-progress.py","status","--composition",output,"--results",checkpoint)
        self.assertEqual(status.returncode,0,status.stderr)
        initial=json.loads(status.stdout)
        self.assertEqual(initial["status"],"partial-resumable")
        self.assertEqual(initial["segments_staged"],0)
        first=receipt["segment_prompt_receipts"][0]
        observed={"schema":"ghostmesh.reasonpack.segment-candidate.v1",
             "segment_index":0,"segment_sha256":first["segment_sha256"],
             "prompt_sha256":first["prompt_sha256"],
             "observations":["Source material discusses a synthetic 3-hour transcript"],
             "source_truth_attested":False,"final_answer_authorized":False}
        candidate_path=self.t/"first-segment.json"
        candidate_path.write_text(json.dumps(observed))
        accepted=run("segment-progress.py","stage","--composition",output,
              "--results",checkpoint,"--index",0,"--candidate",candidate_path)
        self.assertEqual(accepted.returncode,0,accepted.stderr)
        again=run("segment-progress.py","stage","--composition",output,
              "--results",checkpoint,"--index",0,"--candidate",candidate_path)
        self.assertEqual(json.loads(again.stdout)["status"],"already-staged")
        partial=json.loads(run("segment-progress.py","status",
               "--composition",output,"--results",checkpoint).stdout)
        self.assertEqual(partial["segments_staged"],1)
        self.assertEqual(len(partial["missing_indices"]),index["segment_count"]-1)
        self.assertIsNone(partial["actual_billed_cost"])
        self.assertEqual(partial["model_provider"],"UNKNOWN")
        candidate=self.t/"fake-analysis.json"
        d=json.loads((ROOT/"examples/reader-synthetic-analysis.json").read_text())
        candidate.write_text(json.dumps(d))
        hold=run("research-composer.py","validate","--packet",packet,
                 "--registry",reg,"--candidate",candidate,"--out",self.t/"validated.json")
        self.assertEqual(hold.returncode,2)
        self.assertIn("all-segment synthesis receipt",hold.stderr)

    def test_source_video_over_four_hours_not_rejected(self):
        self.pack.rename(self.t/"old")
        self.pack=self.t/"source"
        self.raw=make_pack(self.pack,minutes=260)
        p=self.build()
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertGreater(json.loads(p.stdout)["count"],25)

    def test_no_segments_means_clear_hold_not_duration_rejection(self):
        p=run("editorial-packet.py","--pack",self.pack,"--out",self.t/"missing.json")
        self.assertEqual(p.returncode,2)
        self.assertIn("segment custody",p.stderr)

if __name__=="__main__": unittest.main(verbosity=2)
