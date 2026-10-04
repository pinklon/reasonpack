#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ghostmesh_reasonpack_intake",
    ROOT / "ops" / "ghostmesh-reasonpack-intake.py",
)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


class SlackIntakeUrlTests(unittest.TestCase):
    def test_plain_youtube_url(self):
        text = "watch https://www.youtube.com/watch?v=jNQXAC9IVRw"
        self.assertEqual(
            MOD.youtube_urls(text),
            ["https://www.youtube.com/watch?v=jNQXAC9IVRw"],
        )

    def test_slack_rendered_link_does_not_capture_label(self):
        text = (
            "watch <https://www.youtube.com/watch?v=jNQXAC9IVRw"
            "|youtube.com/watch?v=jNQXAC9IVRw>"
        )
        self.assertEqual(
            MOD.youtube_urls(text),
            ["https://www.youtube.com/watch?v=jNQXAC9IVRw"],
        )

    def test_deduplicates_same_url(self):
        url = "https://youtu.be/jNQXAC9IVRw"
        self.assertEqual(MOD.youtube_urls(f"{url} {url}"), [url])

    def test_non_youtube_url_is_ignored(self):
        self.assertEqual(MOD.youtube_urls("https://example.com/video"), [])


if __name__ == "__main__":
    unittest.main()
