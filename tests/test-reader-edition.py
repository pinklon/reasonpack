#!/usr/bin/env python3
"""Reader navigation and semantic safety contract."""
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reader_edition", ROOT / "ops/reader-edition.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.hrefs = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if "id" in data:
            self.ids.add(data["id"])
        if tag == "a":
            self.hrefs.append(data.get("href", ""))
        if tag == "script":
            self.scripts += 1


class ReaderEditionTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/reader-synthetic-analysis.json").read_text())

    def test_navigation_covers_all_claims_and_valid_targets(self):
        page = mod.render_html(self.data, {"fixture": True}, "a" * 64,
                               {"title": "Fixture video", "channel": "Fixture"})
        parser = Links()
        parser.feed(page)
        self.assertIn("chapters", parser.ids)
        self.assertIn("theme-toggle", parser.ids)
        self.assertIn("source-video", parser.ids)
        self.assertIn("gm-search-input", parser.ids)
        self.assertIn("source", parser.ids)
        self.assertIn("evidence", parser.ids)
        self.assertIn("thesis", parser.ids)
        for i, claim in enumerate(self.data["claims"], 1):
            self.assertIn(f"claim-{i}", parser.ids)
            self.assertIn(claim["statement"], page)
        for href in parser.hrefs:
            if href.startswith("#"):
                self.assertIn(href[1:], parser.ids)
        self.assertEqual(sum("&t=" in href for href in parser.hrefs), 2 * len(self.data["claims"]))
        self.assertIn("gm-site-header", page)
        self.assertIn("gm-site-footer", page)
        self.assertIn("sha256-", page)
        self.assertNotIn("<iframe ", page)

    def test_untrusted_label_is_escaped(self):
        self.data["claims"][0]["statement"] = "<script>alert(1)</script>"
        page = mod.render_html(self.data, {"fixture": True}, "b" * 64, {})
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("PRIVATE DRAFT", page)


if __name__ == "__main__":
    unittest.main()
