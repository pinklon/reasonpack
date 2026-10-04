#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
import tempfile

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

    def test_non_allowed_actor_is_retained_but_not_executed(self):
        with tempfile.TemporaryDirectory() as td:
            state = MOD.open_state(Path(td) / "intake.sqlite3")
            row = {
                "event_id": "event:test",
                "seq": 9,
                "actor_id": "person:someone-else",
                "text": "https://youtu.be/jNQXAC9IVRw",
                "metadata_json": '{"slack":{"channel":"C1","thread_ts":"1.2"}}',
            }
            MOD.create_jobs(state, [row], {"person:tony"})
            status = state.execute("SELECT status FROM jobs WHERE event_id=?", ("event:test",)).fetchone()[0]
            self.assertEqual(status, "ignored_actor")


if __name__ == "__main__":
    unittest.main()
