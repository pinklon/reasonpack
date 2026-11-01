#!/usr/bin/env python3
"""Media normalization decisions, without network or encoder dependencies."""
import importlib.util
import pathlib
import unittest

SPEC = importlib.util.spec_from_file_location("media_plan", pathlib.Path(__file__).resolve().parents[1] / "ops" / "media-plan.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def probe(video="h264", pixel="yuv420p", audio="aac"):
    return {"streams": [
        {"codec_type": "video", "codec_name": video, "pix_fmt": pixel},
        {"codec_type": "audio", "codec_name": audio},
    ]}


class MediaPlanTests(unittest.TestCase):
    def test_copy_compatible(self):
        self.assertEqual(module.modes(probe()), ("copy", "copy"))

    def test_encode_incompatible(self):
        self.assertEqual(module.modes(probe("vp9", "yuv420p", "opus")), ("encode", "encode"))

    def test_independent_audio_decision(self):
        self.assertEqual(module.modes(probe(audio="opus")), ("copy", "encode"))

    def test_pixel_format_requires_normalization(self):
        self.assertEqual(module.modes(probe(pixel="yuv420p10le")), ("encode", "copy"))

    def test_reject_missing_stream(self):
        with self.assertRaises(ValueError):
            module.modes({"streams": [{"codec_type": "video", "codec_name": "h264"}]})


if __name__ == "__main__":
    unittest.main()
