# GhostMesh Mission Plane v0.7: long-form ReasonPack and future paid previews

Status: **source-only candidate, no Production activation, no autonomous model spending, no Gmail send, no payment.**

## Product principle

A GhostMesh request becomes an explicit, inspectable mission. ReasonPack is the first mission type; a website prototype can use the same intake/progress/preview/approval system later.

**No arbitrary video-duration ceiling.** A 10-minute video, three-hour workshop or longer recording may require more units, but the video length itself is not a refusal condition. The total mission can span as many verified work units, human pauses and restarts as necessary. Keep finite limits on each *individual* inference attempt, chunk, process resource allocation, user authorization and cost exposure for safety and reliability.

The current legacy Slack ReasonPack intake still has a 7,200-second acquisition subprocess timeout in `ops/ghostmesh-reasonpack-intake.py`. **That is not removed or qualified by this PR.** It must be replaced by a claim/heartbeat/restart-safe acquisition worker before multi-hour jobs can run unattended; do not claim end-to-end long-form Production support yet.

## Implemented v0.7 components

- `ops/longform-segments.py`: streaming, contiguous UTF-8-safe byte windows, per-segment SHA-256, source manifest binding, start/end offsets, exact reconstruction, immutable output. The number of segments is unbounded; per-segment bytes are deliberately bounded.
- `ops/editorial-packet.py`: for transcripts too large to inline, takes a separately verified segment directory; emits a tiny source-bound packet with a segment-manifest digest rather than copying a huge transcript into one model prompt.
- `ops/reader-pipeline.py`: automatically segments large verified transcripts, records whether input was inline/segmented and the exact segment count. Reuses previously verified segment output on a recovery attempt. Does not mark unfinished work as complete.
- `ops/research-composer.py`: stages one bounded model prompt per segment, with source-byte SHA, index and total segment count. No model invocation. An unreviewed whole-video answer for segmented work remains **HOLD** until an independent all-segment synthesis and review gate is implemented.
- `ops/segment-progress.py`: accepts immutable, source/prompt-bound candidate observations one segment at a time and exposes remaining work; a retry with exact same bytes is idempotent. A staged segment is explicitly **unreviewed**, not a certified answer. No overall processing deadline and no automatic send.
- `ops/mission-receipt.py`: private, portable identity and conservative, read-only telemetry projection for `reasonpack`, `website_preview` and `research` mission types. Any missing provider route, tokens, actual provider bill, customer charge or delivery acceptance remains UNKNOWN/null. The envelope cannot spend funds, promise delivery, send messages or authorize publication.

## Telemetry reuse, not another writer

- GhostMesh Collab **#86** is the authoritative provider-neutral per-response receipt contract and remains Stage 2, gated behind Stage 1 email-quality acceptance.
- Collab **#117** is the independent PRE/POST send witness. A model's journal output cannot attest Gmail acceptance or inbox delivery.
- Collab **#119** owns the optional quiet owner-only email footer, OFF until qualified. The mission projection is a separate **source candidate** and does not display a public footer or duplicate the sender.
- Method labels: verified deterministic transitions may be reported as deterministic. A stage's presence alone does not establish that a model ran. Token usage and actual billed money remain unknown without independent receipts. Do not report $0 from missing information.
- Per-unit telemetry must eventually correlate exact source event, mission, job, segment, attempt and provider receipt hashes. Retries do not silently hide failures or double-count usage.

## Future commercial workflow (concept only)

1. Verified human request with terms and capability scope. Avoid treating an emailed link as permission to spend arbitrarily.
2. GhostMesh qualifies an approved, capped owner-funded pilot or presents an estimate *before expensive work*. An owner may choose an up-front promotional budget, but this is a separate spending authorization and risk decision.
3. Produce a bounded private preview: Reader summary/assessment or a website prototype. Demonstrate value while respecting the requester's data and third-party licensing.
4. Offer an explicit itemized quote and terms, with the deliverable, what is included, ownership/reuse rights, support and failure/refund policy. **No inferred payment authorization and no hidden charges.**
5. Only an affirmative customer payment/contract decision enables a separate payment workflow through an appropriate connected payment processor and audited receipts. This repo has neither processor integration nor permission to collect financial data.
6. Deliver the approved full artifact or hosted result after independent verification. Preserve correction, portability, rollback, support and access-expiry semantics.

A website mission especially requires scoped hosting, domain/DNS authority, customer-provided IP/licensing, deployment permissions, support terms and security review. The showcase cannot silently grant Production website creation.

## Trial and acceptance

- Synthetic 180-minute and 260-minute transcript histories exercise the segmented pipeline, exact hash reconstruction and per-segment prompts. These do **not** prove 3-hour video *media* acquisition or actual 3-hour model reasoning.
- Tampered/missing segments must HOLD. Segment candidates are immutable and resumable. No staged candidate may self-attest semantic support.
- Every mission's `actual_provider_billed_cost_usd` stays null absent independent provider billing, even if a model estimates a likely cost.
- No new Gmail writer, footer, financial account, payment charge, production service, or public route.

## Commissioning gates

- Reconcile original Gmail/Collab #70 / #71 / #86 / #110 / #117 / #119 source writer and exact installed binary before any email integration.
- Replace legacy global acquisition timeout with durable per-stage work claims and heartbeats; implement/source-test a bounded sandboxed multi-segment model executor and independent synthesis/review receipt. No artificial *video-duration* maximum, but explicit resource exhaustion handling and optional owner spending budgets.
- Maintain separate server-side authenticated user-specific previews, quote acceptance and payment ledger only after terms and privacy/security approval.
- Owner-only end-to-end real Gmail request canary with one journal reservation, job/telemetry lineage, one provider-backed send and readback. Gmail acceptance is not inbox arrival.
- All source changes must pass hosted exact-head CI and independent review before merge. Public release requires owner approval of exact content SHA.
