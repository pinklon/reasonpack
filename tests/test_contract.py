#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = (ROOT / "bin" / "reasonpack").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

required = [
    "ghostmesh-reasoning-pack-v1",
    "video.mp4", "audio.m4a", "transcript.txt", "transcript-status.json",
    "source.json", "ffprobe.json", "manifest.json", "SHA256SUMS.txt",
]
for token in required:
    assert token in CLI, token
assert "allowed={'youtube.com','www.youtube.com','m.youtube.com','youtu.be'}" in CLI
assert "actual==allowed" in CLI
assert "reasonpack verify" in README
assert "does not bypass DRM" in README
print("PASS public contract checks")
