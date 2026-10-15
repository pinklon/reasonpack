# Imported Mac ReasonPack v1.0: provenance-preserving custody

This is an additional acquisition/import option, **not a fresh YouTube download**.

## Purpose

A Mac ReasonPack 1.0 package previously acquired and normalized video, audio and timestamped source captions. When the VPS egress path cannot download from YouTube, an authorized owner may transfer the exact Mac evidence bytes over an independently approved private transport.

The importer validates the originating Mac package's complete allowed file inventory, its SHA256SUMS, manifest member lengths and SHA-256 digests, and exact HTTPS video ID. The import produces a new canonical `ghostmesh-reasoning-pack-v1` package without changing the four media/transcript members.

## Provenance

The resulting directory includes:
- byte-identical `video.mp4`, `audio.m4a`, `transcript.srt` and `transcript.txt`
- original manifest, original SHA-256 inventory and the original authoring note
- source.json with the original YouTube metadata and `fresh_youtube_download: false`
- transcript-status.json with source-caption lineage and `caption_accuracy_verified: false`
- fresh local ffprobe metadata and a new canonical manifest/integrity inventory

A manifest checksum proves byte identity under its own trust boundary; it does **not** independently prove YouTube published those bytes, that captions are accurate, or that the video claims are true.

## Execution

```bash
python3 ops/import-verified-mac-pack.py --source /protected/mac-pack \
  --out /protected/verified-vps-pack

./bin/reasonpack verify /protected/verified-vps-pack
python3 tests/test-import-verified-mac-pack.py
```

The destination must not already exist. No live service, worker, credentials, DNS, outbound mail or publication settings are changed by this script.

## October 15, 2026 owner canary

The original Mac evidence for `ZhM29Ds-mBg` was copied using a one-response tailnet HTTP transfer bound to the GhostMesh peer IP and an unpredictable one-use path. The temporary server was closed after the transfer, and the archive SHA-256, original six Mac source checksums, and canonical VPS verifier all passed.

Import receipt for the real video:
- Original Mac manifest SHA-256: `50adf178a50a16656e4aad7218ca5d9153f1e666894bd023ab48e81da3c4d720`
- Canonical VPS manifest SHA-256: `91b14ca132c88981e1f329f9f62af9f844269a7c2ba4c7fa25a3da3cb98f93a4`
- Unchanged video SHA-256: `f6facae446bc370fa511660cccd1ba12da5137cad45e56788367f70a38dd9e19`
- Unchanged transcript SHA-256: `f449b03f94082b6616b0d737d70478775157aa2aac6f5c577e7ccfde814e336f`

A private Reader was generated from that source and validated with a manually curated research register. This confirms real-media-to-private-reader conversion, **not** autonomous source retrieval or email delivery.

## Security/release gates

- The private transfer mechanism was ad hoc and temporary, not an installed unattended acquisition transport. Do not call it Production.
- Persist a trusted independent acquisition receipt if unattended downstream processing will rely on origin guarantees.
- Require independently qualified research retrieval, source corroboration, budget controls and a permitted model runtime before automated facts are released.
- The mail responder's journal/once-only handoff, owner email canary and private reader access gate remain separate.
- Do not merge into main or deploy solely because this imported source and offline fixture tests pass.

Rollback: discard the imported derived folder. The source Mac evidence, existing VPS ReasonPack service and active Gmail responder are unchanged.
