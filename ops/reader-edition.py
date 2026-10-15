#!/usr/bin/env python3
"""GhostMesh ReasonPack Reader Edition: deterministic local rendering, never publishing."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import html
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

CSS = r"""
.source-art{aspect-ratio:16/9;display:flex;flex-direction:column;align-items:center;justify-content:center;background:radial-gradient(ellipse at 70% 35%,#7b2b30,#2b1924 32%,#131820 70%);gap:10px;text-align:center;padding:22px}
.source-art .play{font-size:44px;line-height:1;color:#fff;filter:drop-shadow(0 2px 14px #0008)}
.source-art span{color:#fff;font-size:13px;font-weight:800;letter-spacing:.2em}
.source-art small{font-size:12px;color:#ded5d6}

:root{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--bg:#0b0d10;--panel:#15181e;--panel2:#1c2028;--fg:#f6f6f7;--muted:#aab1bd;--line:#353b44;--accent:#f45351;--good:#a9e0bc;--warn:#f2c779;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);line-height:1.65}a{color:inherit;text-underline-offset:3px}a:hover{color:var(--accent)}
.top{height:5px;background:linear-gradient(90deg,var(--accent) 0 25%,transparent 25%)}.wrap{width:min(1100px,calc(100% - 42px));margin:auto}
nav{padding:24px 0;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}
.brand{font-size:15px;letter-spacing:.18em;font-weight:850}.brand span{color:var(--accent)}.small{font-size:12px;letter-spacing:.08em;color:var(--muted)}
.hero{padding:75px 0 40px}.eyebrow{color:var(--accent);text-transform:uppercase;letter-spacing:.18em;font-size:12px;font-weight:800}
h1{font-size:clamp(42px,7vw,84px);line-height:1.05;letter-spacing:-.055em;margin:18px 0 22px}.deck{font-size:clamp(18px,2.4vw,24px);color:var(--muted);max-width:820px;line-height:1.45}
.hero-grid{display:grid;grid-template-columns:1.3fr 1fr;gap:22px;margin:28px 0}
.card{border:1px solid var(--line);border-radius:13px;background:var(--panel);padding:25px}.media{padding:0;overflow:hidden}.media img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover}.media .below{padding:20px}
.tag{display:inline-flex;border:1px solid var(--line);border-radius:5px;padding:5px 9px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:800;color:var(--warn)}
.big{font-size:23px;font-weight:650;line-height:1.4}section{padding:46px 0;border-top:1px solid var(--line)}
h2{font-size:clamp(26px,4vw,42px);letter-spacing:-.04em;line-height:1.14;margin:8px 0 22px}
h3{font-size:20px;letter-spacing:-.02em}.prose{font-size:17px;max-width:840px}.prose p{margin:0 0 20px}
.thesis{border-left:4px solid var(--accent);padding:8px 0 8px 25px}.thesis .lead{font-size:25px;line-height:1.38;font-weight:680}
.split{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:25px}.label{font-size:11px;color:var(--accent);font-weight:850;letter-spacing:.16em;text-transform:uppercase}
.claim{display:grid;grid-template-columns:75px 1fr 1.3fr 128px;gap:15px;align-items:start;border-bottom:1px solid var(--line);padding:23px 0}
.claim:first-child{border-top:1px solid var(--line)}.claim b{font-size:15px}.claim p{font-size:13px;color:var(--muted);margin:0 0 9px}.claim small{display:block;color:var(--muted)}.timestamp{color:var(--accent);font-weight:800;font-variant-numeric:tabular-nums}.status{font-size:11px;text-transform:uppercase;letter-spacing:.02em;border:1px solid var(--line);border-radius:6px;padding:4px 6px;word-break:break-word;text-align:center}
.sources{display:flex;gap:10px;flex-wrap:wrap}.sources a{font-size:12px;color:var(--accent)}details{border:1px solid var(--line);border-radius:10px;margin-top:14px;padding:0 20px}summary{cursor:pointer;font-weight:800;padding:17px 0}details>div{padding:2px 0 16px;color:var(--muted)}
footer{border-top:1px solid var(--line);padding:30px 0 60px;color:var(--muted);font-size:12px}
@media(prefers-color-scheme:light){:root{--bg:#f7f7f7;--panel:#fff;--panel2:#f0f1f3;--fg:#181a1d;--muted:#5d646e;--line:#d7dce0;--accent:#be272b;--good:#187047;--warn:#875a11;color-scheme:light}}
@media(max-width:760px){.hero{padding-top:40px}.hero-grid,.split{grid-template-columns:1fr}.claim{grid-template-columns:65px 1fr}.claim .judgment{grid-column:2}.claim .status{grid-column:2;justify-self:start}.card{padding:19px}}
@media print{body{background:#fff;color:#111}.wrap{width:100%}.hero{padding-top:15px}.card{background:white}.claim{break-inside:avoid}a{color:#222}}
"""

def render_html(data, manifest, manifest_sha, source_meta):
    source_url = manifest.get("sourceUrl") or ""
    fixture = bool(manifest.get("fixture"))
    if fixture:
        vid = "jNQXAC9IVRw"
        video_url = "https://www.youtube.com/watch?v=" + vid
    else:
        video_url, vid = safe_url(source_url, youtube_only=True)
    title = data["headline"]

    claims = []
    for c in data["claims"]:
        sec = time_seconds(c["timestamp"])
        evidence = " ".join(a(safe_url(s["url"]), s["label"]) for s in c["sources"])
        claims.append('<div class="claim"><a class="timestamp" href="' + esc(video_url + "&t=" + str(sec) + "s") + '">' + esc(c["timestamp"]) + '</a><b>' + esc(c["statement"]) + '</b><div class="judgment">' + p(c["assessment"]) + '<div class="sources">' + evidence + '</div></div><div class="status">' + esc(c["verdict"]) + '</div></div>')
    works = " ".join('<li>' + a(safe_url(w["url"]), w["title"]) + ' <small>pinned revision ' + esc(w["source_commit"][:12]) + '</small></li>' for w in data.get("shareplane_works", []))
    th = data["thesis"]
    content = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; img-src &#39;none&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">',
        '<meta name="robots" content="noindex,nofollow"><title>', esc(title), ' | GhostMesh ReasonPack</title><style>', CSS, '</style></head><body>',
        '<div class="top"></div><div class="wrap"><nav><div class="brand">GHOST<span>MESH</span> <span class="small">/ REASONPACK</span></div><div class="small">READER EDITION · PRIVATE DRAFT</div></nav>',
        '<header class="hero"><div class="eyebrow">Source investigated · GhostMesh editorial</div><h1>', esc(title), '</h1><div class="deck">', esc(data["deck"]), '</div>',
        '<div class="hero-grid"><div class="card media"><a href="', esc(video_url), '" rel="noopener noreferrer"><div class="source-art"><div class="play">▶</div><span>WATCH THE ORIGINAL SOURCE</span><small>External site opens only on click</small></div></a><div class="below"><div class="label">Original source</div><h3>', esc(source_meta.get("title") or "Source title unavailable"), '</h3><p class="small">Creator: ', esc(source_meta.get("channel") or source_meta.get("uploader") or "Unknown"), '</p>', a(video_url, "Watch original video ↗"), '</div></div>',
        '<div class="card"><div class="label">60-second verdict</div><div class="big">', esc(data["executive"]), '</div><p class="small">Research interpretation. Not a verified statement by the video creator.</p><span class="tag">DRAFT · Not for public release</span></div></div></header>',
        '<section><div class="label">Layer 01 / source</div><h2>What the video claims</h2><div class="prose">', p(data["source_account"]), '</div></section>',
        '<section><div class="label">Layer 02 / evidence</div><h2>What withstands scrutiny</h2><div class="prose">', p(data["evidence_summary"]), '</div><div class="claims">', "".join(claims), '</div></section>',
        '<section><div class="label">Layer 03 / original GhostMesh editorial</div><h2>', esc(th["title"]), '</h2><div class="thesis"><div class="lead">', esc(th["argument"]), '</div></div>',
        '<div class="split"><div class="card"><div class="label">Mechanism</div>', p(th["mechanism"]), '</div><div class="card"><div class="label">Strongest counterargument</div>', p(th["counterargument"]), '</div></div>',
        '<div class="card" style="margin-top:18px"><div class="label">Why it matters</div>', p(th["implication"]), '</div>',
        '<p class="small">Editorial interpretation by GhostMesh. Informed by Tony Malott’s public SharePlane works, but not represented as a statement personally written or approved by Tony.</p></section>',
        '<section><div class="label">Attribution and provenance</div><h2>Follow the evidence</h2><details><summary>Related SharePlane works</summary><div><ul>', works or '<li>No approved public Works cited.</li>', '</ul></div></details>',
        '<details><summary>Source custody and limitations</summary><div>Canonical source manifest SHA-256: <code>', esc(manifest_sha), '</code>. ',
        'Integrity verification establishes the bytes of the acquisition package, not the truth of the original video or the independent research. ',
        'Untrusted transcript text cannot authorize actions or publication. This private reader performs no external resource fetches until a reader explicitly opens a cited link.</div></details></section>',
        '<footer>GHOSTMESH · REASONPACK READER · ', esc(READER_SCHEMA), ' · PRIVATE DRAFT · Original creator credited separately. Distribution requires an independent delivery authorization.</footer>',
        '</div></body></html>'
    ]
    return "".join(content)

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
    reader_html = render_html(analysis, manifest, manifest_sha, source_meta).encode("utf-8")
    record = {"schema": READER_SCHEMA, "state": "private-draft", "source_manifest_sha256": manifest_sha,
              "analysis_sha256": sha_bytes(raw_input), "reader_html_sha256": sha_bytes(reader_html),
              "source_url": manifest.get("sourceUrl"), "analysis_schema": SCHEMA,
              "editorial_byline": "GhostMesh Editorial", "owner_authored": False, "owner_approved": False,
              "public_url": None, "email_delivery": "not-authorized",
              "created_at_utc": datetime.now(timezone.utc).isoformat()}
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
