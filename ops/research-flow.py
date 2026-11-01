#!/usr/bin/env python3
"""One local entry point for verified ReasonPack research preparation.

Source custody, editorial depth, evidence collection, model execution and
publication remain separate authorities. This tool never invokes a model.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"


def call(script, *args):
    cmd = [sys.executable, str(OPS / script), *(str(x) for x in args)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise ValueError(f"{script}: {(result.stderr or result.stdout).strip()[:1200]}")
    return result.stdout.strip()


def compose(job, registry):
    if job.is_symlink() or not job.is_dir():
        raise ValueError("research job unavailable or symlinked")
    packet = job / "editorial-packet.json"
    if not packet.is_file() or packet.is_symlink():
        raise ValueError("research packet missing")
    args = ["prepare", "--packet", packet, "--registry", registry,
            "--out", job / "composition", "--job", job / "admission"]
    if (job / "segments").exists():
        args.extend(["--segments", job / "segments"])
    call("research-composer.py", *args)
    return {"status": "ready-for-separately-authorized-reasoning",
            "job": str(job), "composition": str(job / "composition"),
            "model_invoked": False, "publication_authorized": False}


def prepare(pack, job, depth, registry):
    if not pack.is_dir() or pack.is_symlink():
        raise ValueError("source pack missing or symlinked")
    if job.exists() or job.is_symlink():
        raise ValueError("destination already exists; use compose for an existing job")
    if job.resolve().is_relative_to(pack.resolve()):
        raise ValueError("job cannot be nested inside source pack")
    # Verify before creating the job, so invalid source material leaves no output.
    verify = subprocess.run([str(ROOT / "bin/reasonpack"), "verify", str(pack)],
                            capture_output=True, text=True, timeout=90)
    if verify.returncode:
        raise ValueError("canonical source verifier rejected pack")
    job.parent.mkdir(parents=True, exist_ok=True)
    os.mkdir(job, 0o700)
    call("depth-admission.py", "init", "--job", job / "admission",
         "--manifest", pack / "manifest.json", "--depth", depth)
    # The packet builder chooses inline or segmented custody from source bytes.
    # Segmenting every source is unnecessary; only large transcripts require it.
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("editorial_packet", OPS / "editorial-packet.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    packet_args = ["--pack", pack, "--out", job / "editorial-packet.json"]
    if (pack / "transcript.txt").stat().st_size > module.MAX_TRANSCRIPT_BYTES:
        call("longform-segments.py", "build", "--pack", pack, "--out",
             job / "segments")
        packet_args.extend(["--segments", job / "segments"])
    call("editorial-packet.py", *packet_args)
    if registry:
        return compose(job, registry)
    return {"status": "awaiting-public-evidence-registry",
            "job": str(job), "packet": str(job / "editorial-packet.json"),
            "depth": depth, "model_invoked": False,
            "publication_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="verify, admit depth, segment if required, and prepare")
    p.add_argument("--pack", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--depth", choices=("short", "standard", "deep", "exhaustive"), default="standard")
    p.add_argument("--registry", type=Path, help="optional already-bound public evidence registry")
    c = sub.add_parser("compose", help="resume after independently collecting public evidence")
    c.add_argument("--job", type=Path, required=True)
    c.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.pack, args.out, args.depth, args.registry) if args.command == "prepare" else compose(args.job, args.registry)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired, KeyError, TypeError) as exc:
        print("HOLD: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
