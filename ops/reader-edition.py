#!/usr/bin/env python3
"""GhostMesh ReasonPack Reader Edition: deterministic local rendering, never publishing."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import html
from html.parser import HTMLParser
import json
import os
import shutil
import tempfile
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse, parse_qs

SCHEMA = "ghostmesh.reasonpack.analysis.v1"
READER_SCHEMA = "ghostmesh.reasonpack.reader.v1"
VERDICTS = {"supported", "partially-supported", "unsupported", "disputed", "unknown"}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")

def fail(message: str):
    raise ValueError(message)

def clean(value, limit=5000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        fail("required text missing or too long")
    return value.strip()

def esc(v):
    return html.escape(str(v), quote=True)

def safe_url(value, *, youtube_only=False):
    u = urlparse(clean(value, 2048))
    if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
        fail("unsafe external URL")
    host = (u.hostname or "").lower()
    if youtube_only:
        if host not in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"):
            fail("YouTube source host not permitted")
        if host == "youtu.be":
            vid = u.path.strip("/")
        else:
            vid = parse_qs(u.query).get("v", [""])[0] if u.path == "/watch" else ""
        if not ID_RE.fullmatch(vid):
            fail("invalid YouTube video ID")
        return "https://www.youtube.com/watch?v=" + vid, vid
    if not host or host in ("localhost",) or host.endswith((".local", ".internal")):
        fail("external link host not permitted")
    # This renderer never fetches links; links are user-interactive only.
    return u.geturl()

class DeconstructionFragment(HTMLParser):
    tags = set("section h2 h3 h4 p a strong em code pre blockquote ul ol li "
               "table caption thead tbody tfoot tr th td br hr".split())
    void = {"br", "hr"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.stack = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        if tag not in self.tags:
            fail("unsupported deconstruction element: " + tag)
        attrs = dict(attrs)
        attributes = ""
        if tag == "a":
            attributes = f' href="{esc(safe_url(attrs.get("href")))}" rel="noopener noreferrer"'
        elif tag in {"section", "h2", "h3", "h4"} and "id" in attrs:
            anchor = attrs["id"] or ""
            if (not re.fullmatch(r"full-[a-z0-9][a-z0-9_-]{0,127}", anchor)
                    or anchor in self.ids or anchor == "full-deconstruction"):
                fail("invalid or repeated deconstruction anchor")
            self.ids.add(anchor)
            attributes = f' id="{anchor}"'
        elif tag == "table":
            self.parts.append('<div class="rp-table-scroll" role="region" aria-label="Table" tabindex="0">')
            attributes = ' class="comparison"'
        self.parts.append(f"<{tag}{attributes}>")
        if tag not in self.void:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            fail("unbalanced deconstruction fragment")
        self.parts.append(f"</{tag}>")
        if tag == "table":
            self.parts.append("</div>")

    def handle_data(self, data):
        self.parts.append(esc(data))

    def handle_decl(self, declaration):
        fail("expected a deconstruction HTML fragment")


def render_deconstruction(source):
    parser = DeconstructionFragment()
    parser.feed(clean(source, 512 * 1024))
    parser.close()
    if parser.stack:
        fail("unbalanced deconstruction fragment")
    return ('<section class="full-deconstruction" id="full-deconstruction">'
            '<h2>Full deconstruction</h2>' + ''.join(parser.parts) + '</section>')


def time_seconds(v):
    if not isinstance(v, str) or not TIME_RE.fullmatch(v):
        fail("invalid video timestamp")
    parts = [int(x) for x in v.split(":")]
    if (len(parts)==2 and parts[1]>59) or (len(parts)==3 and (parts[1]>59 or parts[2]>59)):
        fail("out-of-range video timestamp")
    return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]

def sha_bytes(raw):
    return sha256(raw).hexdigest()

def assert_canonical_pack(pack: Path, repo: Path):
    if not pack.is_dir() or pack.is_symlink():
        fail("pack must be a real directory")
    script = Path(__file__).with_name("reasonpack")
    if not script.is_file():
        script = repo / "bin" / "reasonpack"
    p = subprocess.run([str(script), "verify", str(pack)], capture_output=True, text=True, timeout=45)
    if p.returncode:
        fail("canonical ReasonPack verification failed")
    raw = (pack / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    if manifest.get("schema") != "ghostmesh-reasoning-pack-v1":
        fail("unsupported canonical pack schema")
    for member in manifest.get("members", []):
        if member.get("path") == "transcript.txt":
            break
    else:
        fail("verified pack missing transcript")
    return manifest, sha_bytes(raw)

def load_analysis(path):
    data = json.loads(path.read_text("utf-8"))
    if data.get("schema") != SCHEMA:
        fail("incorrect analysis schema")
    for field in ("headline", "deck", "executive", "source_account", "evidence_summary"):
        clean(data.get(field), 15000 if field in ("source_account", "evidence_summary") else 5000)
    claims = data.get("claims")
    if not isinstance(claims, list) or not (1 <= len(claims) <= 30):
        fail("reader requires 1-30 claims")
    for claim in claims:
        if not isinstance(claim, dict):
            fail("invalid claim object")
        for k in ("timestamp", "statement", "assessment"):
            clean(claim.get(k), 3500)
        time_seconds(claim["timestamp"])
        if claim.get("verdict") not in VERDICTS:
            fail("unknown verdict")
        sources = claim.get("sources")
        if not isinstance(sources, list) or len(sources) > 12:
            fail("invalid source list")
        if claim["verdict"] == "supported" and not sources:
            fail("supported claims require independent source citations")
        for src in sources:
            if not isinstance(src, dict):
                fail("invalid source object")
            clean(src.get("label"), 180)
            safe_url(src.get("url"))
    thesis = data.get("thesis")
    if not isinstance(thesis, dict):
        fail("missing editorial thesis")
    for field in ("title", "argument", "mechanism", "counterargument", "implication"):
        clean(thesis.get(field), 7500)
    works = data.get("shareplane_works", [])
    if not isinstance(works, list) or len(works) > 12:
        fail("invalid related Works")
    for work in works:
        if not isinstance(work, dict):
            fail("invalid Work citation object")
        clean(work.get("title"), 220)
        u = safe_url(work.get("url"))
        if urlparse(u).hostname != "shareplane.malott.ai":
            fail("SharePlane citation must be public canonical origin")
        if not SHA_RE.fullmatch(work.get("source_commit", "")):
            fail("SharePlane Works require pinned commit SHA")
    return data

def p(text):
    # No Markdown interpretation and no HTML from untrusted evidence or analysis.
    return "<p>" + esc(text).replace("\n", "<br>") + "</p>"

def a(url, label, css=""):
    return '<a rel="noopener noreferrer" target="_blank" class="' + css + '" href="' + esc(url) + '">' + esc(label) + '</a>'

def render_html(data, manifest, manifest_sha, source_meta, companion_url=None, continuing=(),
                deconstruction=None):
    if manifest.get("fixture"):
        vid = "jNQXAC9IVRw"
        video_url = "https://www.youtube.com/watch?v=" + vid
    else:
        video_url, vid = safe_url(manifest.get("sourceUrl"), youtube_only=True)
    title = esc(data["headline"])
    deck = esc(data["deck"])
    source_title = esc(source_meta.get("title") or "Original source")
    creator = esc(source_meta.get("channel") or source_meta.get("uploader") or "Unknown creator")
    chapters, claims = [], []
    for index, claim in enumerate(data["claims"], start=1):
        sec = time_seconds(claim["timestamp"])
        timestamp = esc(claim["timestamp"])
        seek_url = video_url + "&t=" + str(sec) + "s"
        statement = esc(claim["statement"])
        chapters.append(
            f'<a data-seek="{sec}" href="{esc(seek_url)}"><time>{timestamp}</time>'
            f'<span>{statement}</span></a>'
        )
        refs = " · ".join(a(safe_url(s["url"]), s["label"]) for s in claim["sources"])
        claims.append(
            f'<details id="claim-{index}"><summary><span class="gm-claim-label">'
            f'<span class="gm-claim-status">{esc(claim["verdict"].replace("-", " ").capitalize())}</span>'
            f'</span><span class="gm-claim-proposition">{statement}</span></summary>'
            f'<div class="gm-claim-detail">{p(claim["assessment"])}'
            f'<p>{a(seek_url, "Watch on YouTube at " + claim["timestamp"])}</p>'
            + (f'<p>Evidence: {refs}</p>' if refs else '')
            + '</div></details>'
        )
    works = [
        '<li>' + a(safe_url(w["url"]), w["title"]) + ' <small>pinned revision '
        + esc(w["source_commit"][:12]) + '</small></li>'
        for w in data.get("shareplane_works", [])
    ]
    thesis = data["thesis"]
    related = (
        '<section class="gm-related" id="related-thinking"><p class="gm-kicker">Continue the inquiry</p>'
        '<h2>Related thinking</h2>'
        + ('<ul>' + ''.join(works) + '</ul>' if works else
           '<p>This private draft has no approved graph relationships.</p>')
        + '</section>'
    )
    if len(continuing) > 12:
        fail("too many continuing readings")
    cards = []
    for label, label_title, url, reason in continuing:
        clean(label, 120)
        clean(label_title, 220)
        clean(reason, 600)
        cards.append(
            f'<article class="related-item"><small>{esc(label)}</small>'
            f'{a(safe_url(url), label_title)}<p>{esc(reason)}</p></article>'
        )
    if deconstruction is not None:
        companion_url = None
    follow = ''
    if cards or companion_url:
        follow = (
            '<section class="appendix" id="related"><p class="eyebrow">In context / proposed editorial connections</p>'
            '<h2>Continue the thinking</h2>'
            + ('<p>These reading suggestions develop adjacent arguments. They are editorial connections for this draft.</p>'
               '<div class="related-grid">' + ''.join(cards) + '</div>' if cards else '')
            + ('<p class="fine">' + a(safe_url(companion_url), "Full deconstruction and related SharePlane works")
               + '</p>' if companion_url else '')
            + '</section>'
        )
    brief = (
        '<section class="gm-brief" id="at-a-glance" aria-labelledby="brief-title">'
        '<div class="gm-brief-heading"><p class="gm-kicker">The reading / in three moves</p>'
        '<h2 id="brief-title">Start with the distinction.</h2></div>'
        + ''.join(
            f'<div class="gm-brief-point"><span class="gm-brief-index">{i:02d}</span>'
            f'<div><h3>{heading}</h3><p>{esc(value)}</p></div></div>'
            for i, (heading, value) in enumerate((
                ("What the video is about", data["deck"]),
                ("Why you should care", data["executive"]),
                ("What GhostMesh takes away", thesis["implication"]),
            ), 1)
        ) + '</section>'
    )
    if deconstruction is not None:
        body = render_deconstruction(deconstruction)
        body_nav = '<a href="#full-deconstruction">Full deconstruction</a>'
    else:
        body = (
            '<section id="source"><h2>What the video claims</h2>' + p(data["source_account"]) + '</section>'
            '<section class="gm-evidence" id="evidence"><div class="gm-evidence-intro">'
            '<p class="gm-kicker">Claim register</p><h2>Corroboration and counterevidence</h2>'
            + p(data["evidence_summary"]) + '</div><div class="gm-evidence-body"><div class="gm-claim-list">'
            + ''.join(claims) + '</div></div></section>'
            f'<section id="thesis"><h2>{esc(thesis["title"])}</h2>' + p(thesis["argument"])
            + '<h3>Mechanism</h3>' + p(thesis["mechanism"])
            + '<h3>Strongest counterargument</h3>' + p(thesis["counterargument"])
            + '<h3>Implication</h3>' + p(thesis["implication"]) + '</section>'
            + '<section id="provenance"><details><summary>Source custody and review status</summary>'
            f'<p>Verified acquisition manifest SHA-256: <code>{esc(manifest_sha)}</code>.</p>'
            '<p>Private editorial draft. Claim verdicts describe the cited evidence. Owner editorial acceptance is pending.</p>'
            '</details></section>'
        )
        body_nav = (
            '<a href="#source">Source account</a>'
            '<a href="#evidence">Claim register</a><a href="#thesis">Interpretation</a>'
            '<a href="#provenance">Provenance</a>'
        )
    article = (
        brief + '<header class="hero"><p class="eyebrow">GhostMesh / ReasonPack / Video deconstruction</p>'
        f'<h1>{title}</h1><p class="lead">{deck}</p><div class="meta">'
        f'<span>{creator}</span><span class="gm-private-draft">PRIVATE DRAFT</span>'
        '<span>GhostMesh editorial</span></div></header>'
        '<div class="reading"><article class="prose">'
        '<section id="film"><h2>Watch the original argument</h2>'
        '<div class="player gm-media-frame" data-gm-aspect="16:9">'
        f'<div id="source-video" style="position:absolute;inset:0" data-video-id="{esc(vid)}"></div>'
        f'<button class="source-launch" type="button" id="launch" hidden><span class="gm-player-source-title">{source_title}</span>'
        ' ▶ Play the original video</button></div>'
        f'<p class="caption">{a(video_url, "Open the original on YouTube")}. '
        'Seek times are approximate. Each claim also has a direct YouTube link.</p>'
        '<nav id="chapters" class="chapter-guide" aria-label="Seek within the source video">'
        '<h3>Jump to a part of the conversation</h3>'
        '<p class="caption">Choose a passage to start the player at its timestamp.</p>'
        '<div class="chapter-grid">' + ''.join(chapters) + '</div></nav></section>'
        + body + related + follow + '</article><aside class="rail"><nav aria-label="In this reading">'
        '<a href="#at-a-glance">At a glance</a><a href="#film">Source video</a>'
        '<a href="#chapters">Timestamps</a>' + body_nav
        + '<a href="#related-thinking">Related thinking</a>'
        + ('<a href="#related">Continue the thinking</a>' if follow else '') + '</nav></aside></div>'
    )
    template = Path(__file__).with_name("reader-current-shell.html").read_text("utf-8")
    if deconstruction is not None:
        css = (
            ".full-deconstruction{overflow-wrap:anywhere}"
            ".full-deconstruction section{margin:2.5rem 0;scroll-margin-top:100px}"
            ".rp-table-scroll{overflow:auto;max-width:100%;margin:1.5rem 0}"
        )
        template = template.replace("</style>", css + "</style>", 1)
    slots = {"TITLE": title, "ARTICLE": article}
    return re.sub(r"@@(TITLE|ARTICLE)@@", lambda match: slots[match[1]], template)



def atomic_write(path: Path, raw: bytes):
    if path.exists():
        fail("output already exists; edition is immutable, use a new directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    with tmp.open("xb") as f:
        f.write(raw)
    tmp.replace(path)

def build(args):
    repo = Path(__file__).resolve().parents[1]
    manifest, manifest_sha = assert_canonical_pack(args.pack, repo)
    analysis = load_analysis(args.analysis)
    source_meta = json.loads((args.pack / "source.json").read_text("utf-8"))
    if not isinstance(source_meta, dict):
        fail("invalid canonical source metadata")
    if manifest.get("fixture"):
        if not args.allow_fixture:
            fail("synthetic source pack cannot be used without --allow-fixture")
    else:
        src_url, vid = safe_url(manifest["sourceUrl"], youtube_only=True)
        if analysis.get("video_id") != vid:
            fail("analysis source ID does not match canonical pack")
        if source_meta.get("id") != vid:
            fail("source metadata ID does not match canonical pack")
    if args.out.exists():
        fail("edition destination already exists; use a new version")
    raw_input = args.analysis.read_bytes()
    full_path = getattr(args, "deconstruction_html", None)
    full_input = full_path.read_bytes() if full_path is not None else None
    reader_html = render_html(
        analysis, manifest, manifest_sha, source_meta, getattr(args, "companion_url", None),
        getattr(args, "continue_reading", ()),
        deconstruction=full_input.decode("utf-8") if full_input is not None else None,
    ).encode("utf-8")
    record = {"schema": READER_SCHEMA, "state": "private-draft", "source_manifest_sha256": manifest_sha,
              "analysis_sha256": sha_bytes(raw_input), "reader_html_sha256": sha_bytes(reader_html),
              "reader_design": "ghostmesh-editorial-v1",
              "reader_shell_sha256": sha_bytes(Path(__file__).with_name("reader-current-shell.html").read_bytes()),
              "source_url": manifest.get("sourceUrl"), "analysis_schema": SCHEMA,
              "editorial_byline": "GhostMesh Editorial", "owner_authored": False, "owner_approved": False,
              "public_url": None, "email_delivery": "not-authorized",
              "created_at_utc": datetime.now(timezone.utc).isoformat()}
    if full_input is not None:
        record["deconstruction_sha256"] = sha_bytes(full_input)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".reader-stage-", dir=args.out.parent))
    try:
        (staging / "index.html").write_bytes(reader_html)
        (staging / "reader-receipt.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
        if args.out.exists():
            fail("edition destination appeared during rendering")
        os.rename(staging, args.out)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(json.dumps({"result": "private-draft", "reader": str(args.out / "index.html"),
                      "receipt": str(args.out / "reader-receipt.json"), "sha256": record["reader_html_sha256"]}))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--analysis", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    editorial = ap.add_mutually_exclusive_group()
    editorial.add_argument("--companion-url", help="optional HTTPS link to a companion report")
    editorial.add_argument("--deconstruction-html", type=Path,
                           help="complete editorial HTML fragment to render inline")
    ap.add_argument("--continue-reading", action="append", nargs=4, default=[],
                    metavar=("LABEL", "TITLE", "URL", "REASON"),
                    help="proposed editorial reading connection; may be repeated")
    ap.add_argument("--allow-fixture", action="store_true", help="development tests only")
    args = ap.parse_args()
    try:
        build(args)
    except (ValueError, FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError) as exc:
        print("REJECTED: " + str(exc), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
