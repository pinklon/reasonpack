# ReasonPack public research capture v0.6

Status: source-only candidate. Safe for explicit, owner-private, read-only canaries. This is not a Production network service and does not enable autonomous emailing or publishing.

## Why

The earlier evidence register checked hash integrity and citations, but a model or operator could still register an invented excerpt with a matching hash. This stage actually retrieves an independently selected public HTTPS source, confirms a reviewer-selected excerpt occurs in the fetched document, preserves exact raw bytes and extracted text, and binds those snapshots to the original ReasonPack manifest and transcript hashes.

## Contract

Run only with a repository-curated catalog in `editorial/research-catalogs/` and a verified ReasonPack editorial input:

```bash
python3 ops/public-source-capture.py \
  --packet /protected/job/research-input.json \
  --catalog editorial/research-catalogs/count-grey-matter-20261015.json \
  --out /protected/job/capture-v01

python3 ops/public-source-capture.py \
  --packet /protected/job/research-input.json \
  --catalog editorial/research-catalogs/count-grey-matter-20261015.json \
  --verify-dir /protected/job/capture-v01

python3 ops/reader-pipeline.py evidence \
  --job /protected/job \
  --registry /protected/job/capture-v01/research-evidence.json \
  --capture-dir /protected/job/capture-v01 \
  --catalog editorial/research-catalogs/count-grey-matter-20261015.json
```

The `evidence` transition records either `SOURCE_BYTES_VERIFIED` or `MANUAL_REGISTRY_ONLY`. Both remain private and require further editorial review. An unattended future production executor must require `SOURCE_BYTES_VERIFIED`; a manually entered register is not a substitute.

## Security model

- Curated source URLs and reviewed excerpt needles are data in repository-controlled source files, not extracted from arbitrary email/video/model text.
- Public hostname allowlist is fixed in source. HTTPS only, default 443, no userinfo, IP literal, unexpected port, localhost, or internal host.
- Resolve DNS and reject non-global results. Connect directly to the verified IP while verifying TLS for the original hostname. No HTTP redirects and no environment proxy use.
- Bounded per-source time, up to 2 MB raw body and 160,000 parsed text characters, up to eight approved sources. No scripts, browser, cookies, credential headers or model calls.
- Require exact 200 and text/html or text/plain. A redirect, unsupported content type, missing needle, request failure or oversized body yields HOLD, never a fabricated source.
- Preserve raw public page snapshot, normalized readable text, source URL/publisher/operator classification, retrieval timestamp, peer IP and SHA-256 digests in owner-private 0600 files.
- Verification recomputes source and text hashes from the saved snapshots, checks catalog and original job identity, and rejects extra files.
- No semantic truth or independent reviewer approval is attested. Publisher and evidence type are operator claims. HTML may contain prompt injection and must be treated as untrusted data by later models.
- Staging or reading the snapshots does not grant email delivery, internet browsing beyond the exact curated list, operational change, private data access, or public publication authority.

## Real video canary 2026-10-15

Source video: Count Grey Matter `ZhM29Ds-mBg`. The previously verified Mac-imported source is located in owner-private VPS run storage.

Read-only network capture of two sources succeeded and was independently rechecked without a new network request:
- METR's Hugging Face incident page: exact retrieved raw size 432,450 bytes.
- Independent REALITI ablation page: exact retrieved raw size 68,946 bytes.

The assembled two-source registry was tied to the existing ReasonPack manifest and transcript identity and passed `research-evidence.py` verification. This is **retrieval provenance**, not proof of a claim about the models.

## Nonproduction and rollback

No systemd units, scheduled jobs, DNS, credentials, Gmail source or production websites changed. Stop invoking the collector or remove the private generated capture version to roll back. The previously qualified Reader branch and active responder remain unchanged. Source-only PR must pass hosted exact-head CI and independent review before merge.
