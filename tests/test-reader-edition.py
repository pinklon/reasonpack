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

    def test_editorial_connections_stay_separate_from_claim_evidence(self):
        page = mod.render_html(self.data, {"fixture": True}, "a" * 64, {},
                               continuing=[("Parallel work", "Adjacent Reader",
                                            "https://youtube.shareplane.malott.ai/example/",
                                            "<em>Reason</em>")])
        self.assertLess(page.index('id="at-a-glance"'), page.index('<h1>'))
        self.assertLess(page.index('id="related-thinking"'), page.index('id="related"'))
        self.assertNotIn("Adjacent Reader", page.split('id="related"')[0])
        self.assertIn("&lt;em&gt;Reason&lt;/em&gt;", page)

    def test_full_deconstruction_is_rendered_inline(self):
        article = (
            '<section id="full-argument"><h2>Complete argument</h2>'
            '<p onclick="alert(1)">Evidence &amp; limits.<br />An example.</p>'
            '<table><tr><td>Verified outcome</td></tr></table></section>'
        )
        page = mod.render_html(self.data, {"fixture": True}, "a" * 64, {},
                               deconstruction=article)
        self.assertIn('href="#full-deconstruction"', page)
        self.assertIn('id="full-argument"', page)
        self.assertIn('Evidence &amp; limits.<br>An example.', page)
        self.assertIn('Verified outcome', page)
        self.assertIn('class="rp-table-scroll"', page)
        self.assertIn('id="chapters"', page)
        self.assertNotIn('id="evidence"', page)
        self.assertNotIn('onclick="alert(1)"', page)
        for unsafe in ('<script>bad</script>', '<a href="javascript:bad">bad</a>',
                       '<section id="related-thinking"></section>', '<p>unfinished'):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                mod.render_deconstruction(unsafe)

    def test_untrusted_label_is_escaped(self):
        self.data["claims"][0]["statement"] = "<script>alert(1)</script>"
        page = mod.render_html(self.data, {"fixture": True}, "b" * 64, {})
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("PRIVATE DRAFT", page)


if __name__ == "__main__":
    unittest.main()
