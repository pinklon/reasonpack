# ReasonPack streaming integrity upgrade v0.11

State: **source-only candidate, no installer, no Production CLI replacement, no new video download, no Gmail/Slack writer change**.

## Defect addressed

The original `bin/reasonpack` script built and verified package manifests by computing SHA-256 over `open(path, 'rb').read()`. Video, audio and long caption members could therefore consume memory proportional to media file size, despite the CLI and ReasonPack's chunked downstream reasoning contract.

This source increment replaces all five unbounded whole-file SHA paths in the build, verifier and self-test Python heredocs with a fixed 1 MiB streaming hash loop. The CLI remains self-contained with no new runtime Python dependency.

The verifier also validates flat, safe filenames, refuses symlinked members/metadata/roots, rejects duplicate or missing members and requires one complete inventory of unique SHA-256 members, rather than trusting arbitrary path entries in untrusted manifest JSON.

## Qualification

The new `tests/test-streaming-integrity.py` constructs a sparse 128 MiB synthetic video-shaped byte member and runs `bin/reasonpack verify` inside a subprocess with a **72 MiB virtual-memory limit**. A full verification succeeds in that limit and an altered byte near the end fails. Other tests cover length inconsistency, checksum tampering, member symlinks, path traversal, duplicate and missing inventory entries, and the ordinary preexisting fixture.

The sparse bytes are not playable footage. A successful streaming hash proves bounded *hash memory*, not ffmpeg/yt-dlp long-video resilience, true source origin or a finished reasoning job.

## Worker pin transition

`ops/acquisition-real-worker.py` now requires the candidate CLI SHA-256:

`2b9773f76223f4f7fe37b222c8b16639f41c4a692c350794338263ef25a214b1`

The currently installed VPS `/home/ghostmesh/.local/share/reasonpack/reasonpack` still has the old digest `3fb0e0b7b4eb0977671b12de9b28d9a41fa6f539a2b0ba6e426f6643238b6fef`. **Preflight MUST reject that installed binary until a separately reviewed and owner-authorized immutable CLI release has been installed and read back.** Do not overwrite or mutate the live symlink from this PR.

## Boundaries and remaining work

This upgrade removes memory proportional to *file size* from source hashing, not the need for finite per-process resource protections and model context windows. No overall video-duration ceiling is added. Streaming over very large data may require considerable wall time and disk I/O; the live verifier and transcoder still need progress witnesses, independently controlled cancellation and rollback before commissioning.

The host exposes cgroup v2, but the executing service account cannot directly create delegated child cgroups. Strong containment of all descendants of yt-dlp/ffmpeg therefore needs an owner-controlled systemd delegated scope or equivalent reviewed authority. Existing source-only worker progress and potential orphan detection do not confer automatic kill rights.

No live ReasonPack poller, Gmail responder, old `timeout=7200`, provider credentials, payment or public Reader is changed in this source PR. Every output in this candidate stays private and uncommissioned.

## Run

```bash
bash -n bin/reasonpack
./bin/reasonpack self-test
./bin/reasonpack verify examples/sample-reasonpack
python3 tests/test-streaming-integrity.py
```

Hosted exact-head CI and independent review required. The next owner action after source qualification is a separate immutable CLI installer and an isolated multi-hour or large-file acquisition/cgroup canary with exact original source preservation and verified rollback. No Production promotion on source CI alone.
