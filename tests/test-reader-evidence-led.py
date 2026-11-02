#!/usr/bin/env python3
"""Opt-in evidence-led Reader contract. Classic mode must remain unchanged."""
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reader_edition", ROOT / "ops/reader-edition.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
        self.hrefs=[]
        self.scripts=0
        self.forms=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if "id" in d: self.ids.add(d["id"])
        if tag=="a": self.hrefs.append(d.get("href", ""))
        if tag=="script": self.scripts+=1
        if tag=="form": self.forms.append(d)

class EvidenceLedTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT / "examples/reader-synthetic-analysis.json").read_text())
        self.data["claims"].append({
            "timestamp":"00:10", "statement":"Second claim", "assessment":"Partially supported.",
            "verdict":"partially-supported",
            "sources":[{"label":"Primary paper","url":"https://arxiv.org/abs/2406.11717"}]})
        self.data["claims"][0]["sources"]=[{"label":"Primary paper","url":"https://arxiv.org/abs/2406.11717"}]
        self.data["shareplane_works"]=[{"title":"Approved Work","url":"https://shareplane.malott.ai/works/example","source_commit":"a"*40}]
    def page(self, variant):
        return mod.render_html(self.data, {"fixture":True}, "b"*64, {"title":"Fixture"}, variant=variant)
    def test_variant_search_relationships_and_security(self):
        page=self.page("evidence-led")
        parsed=Parser()
        parsed.feed(page)
        self.assertEqual(parsed.scripts,1)
        self.assertTrue({"reader-search","claim-search","claim-search-clear","corroboration","theme-switch"}.issubset(parsed.ids))
        self.assertIn("script-src &#39;unsafe-inline&#39;",page)
        self.assertIn("form-action https://youtube.shareplane.malott.ai",page)
        self.assertIn("https://youtube.shareplane.malott.ai/readers/",str(parsed.forms))
        self.assertIn("Approved Work",page)
        self.assertEqual(page.count('class="relation"'),1)
        self.assertEqual(page.count('class="relation-links"'),1)
        self.assertIn("C01",page)
        self.assertIn("C02",page)
        self.assertIn("No SharePlane Work relationship is inferred",page)
        for href in parsed.hrefs:
            if href.startswith("#"): self.assertIn(href[1:],parsed.ids)
    def test_classic_unchanged(self):
        default=mod.render_html(self.data, {"fixture":True}, "b"*64, {"title":"Fixture"})
        self.assertEqual(default,self.page("classic"))
        self.assertNotIn("reader-search",default)
        self.assertNotIn("<script>",default)
        self.assertIn("form-action &#39;none&#39;",default)
    def test_escaping_and_no_fake_relationships(self):
        self.data["claims"][1]["sources"][0]["label"]="<script>bad</script>"
        page=self.page("evidence-led")
        self.assertNotIn("<script>bad</script>",page)
        self.assertIn("&lt;script&gt;bad&lt;/script&gt;",page)
        self.assertEqual(page.count('class="relation"'),2)
    def test_unknown_variant_rejected(self):
        with self.assertRaises(ValueError):
            self.page("unregistered")

if __name__=="__main__":
    unittest.main()
