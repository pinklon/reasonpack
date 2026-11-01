#!/usr/bin/env python3
"""Bounded, source-derived navigation cues from verified private VTT captions.

No network, video-duration cap, model call or publication. A sampled cue is a
seek aid, not proof of the assertion or of the speaker's exact word timing.
"""
from __future__ import annotations
import html
from hashlib import sha256
import re
from pathlib import Path

START=re.compile(r"^(\d{2,}:\d\d:\d\d)\.\d{3}\s+-->")
TAG=re.compile(r"<[^>]*>")
MAX_CUES=480
MAX_WORDS=16

def from_vtt(path:Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("captions must be a regular source-pack file")
    raw=path.read_bytes()
    if not raw.startswith(b"WEBVTT"):
        raise ValueError("unsupported timestamped caption format")
    cues=[]
    for block in re.split(r"\r?\n\s*\r?\n",raw.decode("utf-8-sig")):
        lines=block.splitlines()
        row=next((i for i,x in enumerate(lines) if START.match(x)),None)
        if row is None:continue
        match=START.match(lines[row])
        words=" ".join(html.unescape(TAG.sub("",line)).strip() for line in lines[row+1:])
        words=" ".join(words.split())
        if not words:continue
        clipped=" ".join(words.split()[:MAX_WORDS])
        if cues and cues[-1]["cue"]==clipped:continue
        cues.append({"at":match.group(1),"cue":clipped})
    if not cues:raise ValueError("caption file contains no timed spoken cues")
    if len(cues)>MAX_CUES:
        # Even sampling maintains whole-source navigation without a duration
        # cutoff; coverage is explicitly marked sampled, not exhaustive.
        count=len(cues)
        selected=[cues[i*(count-1)//(MAX_CUES-1)] for i in range(MAX_CUES)]
    else:selected=cues
    return {"caption_sha256":sha256(raw).hexdigest(),
            "caption_cues_total":len(cues),
            "timeline_sampled":len(cues)>MAX_CUES,
            "navigation_cues":selected}
