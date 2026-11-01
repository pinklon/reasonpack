#!/usr/bin/env python3
"""Private caption timecode extraction regression."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("caption_timeline",ROOT/"ops/caption-timeline.py")
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
class TimelineTests(unittest.TestCase):
 def test_cues_preserve_source_time_and_strip_markup(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"captions.vtt"
   p.write_text("WEBVTT\n\n00:00:02.100 --> 00:00:05.000\nHello<00:00:03.000><c> world</c>\n\n00:00:12.000 --> 00:00:15.000\nSecond cue\n")
   obj=M.from_vtt(p)
   self.assertEqual([x["at"] for x in obj["navigation_cues"]],["00:00:02","00:00:12"])
   self.assertEqual(obj["navigation_cues"][0]["cue"],"Hello world")
   self.assertFalse(obj["timeline_sampled"])
 def test_long_caption_custody_uses_whole_source_sampling(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"captions.vtt"
   segments=["WEBVTT"]
   for i in range(2000):
    segments.append(f"{i//3600:02d}:{i//60%60:02d}:{i%60:02d}.000 --> 00:59:59.999\nUnique spoken cue number {i}")
   p.write_text("\n\n".join(segments))
   obj=M.from_vtt(p)
   self.assertEqual(obj["caption_cues_total"],2000)
   self.assertEqual(len(obj["navigation_cues"]),M.MAX_CUES)
   self.assertEqual(obj["navigation_cues"][0]["at"],"00:00:00")
   self.assertEqual(obj["navigation_cues"][-1]["at"],"00:33:19")
   self.assertTrue(obj["timeline_sampled"])
 def test_missing_timed_cues_rejects(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"captions.vtt";p.write_text("WEBVTT\n\nUntimed content")
   with self.assertRaises(ValueError):M.from_vtt(p)
if __name__=="__main__":unittest.main()
