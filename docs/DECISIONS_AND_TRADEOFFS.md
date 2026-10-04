# Design Decisions and Tradeoffs

This is a compact decision record for choices that are easy to “simplify” later in ways that quietly change the product.

## D1 — admit YouTube only in v1

**Decision:** URL validation allows a small explicit set of YouTube hosts.

**Why:** the product needs one well-understood source boundary more than it needs generic downloader breadth.

**Tradeoff:** less convenient for Vimeo, training portals and arbitrary media URLs.

**Revisit when:** another source class has real demand and an explicit acquisition/rights/test model.

## D2 — no playlist expansion

**Decision:** every acquisition command uses `--no-playlist`.

**Why:** one invocation should correspond to one source identity and bounded cost.

**Tradeoff:** batch learning playlists require repeated calls today.

**Revisit when:** batch semantics include per-source identity, failure isolation and output structure.

## D3 — captions before Whisper

**Decision:** prefer available source subtitles/automatic captions; use Whisper only as explicit fallback.

**Why:** source captions provide a direct evidence path and avoid unnecessary inference/cost.

**Tradeoff:** automatic captions can be lower quality than a strong local speech model.

**Mitigation:** record transcript provenance so downstream users can decide when retranscription is warranted.

## D4 — Whisper is explicit, local and optional

**Decision:** no automatic model install/download.

**Why:** model size, licensing, performance, endpoint policy and data sensitivity vary.

**Tradeoff:** some users with captionless sources need extra setup.

## D5 — normalize media

**Decision:** produce H.264/AAC MP4 plus AAC audio rather than retaining arbitrary source formats as the core interface.

**Why:** downstream tools benefit from predictable formats.

**Tradeoff:** transcoding costs time/CPU and changes bytes from the original remote media representation.

**Mitigation:** preserve source metadata and clearly call outputs normalized analysis copies, not original archival masters.

## D6 — close the pack under its manifest

**Decision:** verifier rejects unexplained regular files.

**Why:** prevents source evidence and derived analysis from blurring together over time.

**Tradeoff:** users cannot casually drop notes into the same directory without failing verification.

**Mitigation:** document a sibling derived-analysis pattern.

## D7 — hashes are integrity, not truth

**Decision:** documentation consistently limits SHA-256 claims to byte identity.

**Why:** cryptographic vocabulary tends to inflate trust claims if left unchecked.

**Tradeoff:** requires more explicit explanation to non-security readers.

## D8 — no automatic upload

**Decision:** ReasonPack ends at local artifact creation/verification.

**Why:** storage introduces credentials, sharing, retention and organizational-policy boundaries.

**Tradeoff:** user must choose/call a storage path separately.

**Revisit when:** a storage adapter can preserve exact bytes and readback evidence without becoming the product’s identity plane.

## D9 — WSL before native Windows

**Decision:** use WSL as the current Windows route.

**Why:** reuses the Bash/Linux runtime and limits implementation divergence during early adoption.

**Tradeoff:** WSL may be disallowed or undesirable on some enterprise endpoints.

**Revisit when:** Windows adoption earns the maintenance cost of a native runtime.

## D10 — no AI summary in the canonical v1 pack

**Decision:** current pack is source-evidence oriented.

**Why:** derived reasoning has different provenance and can change with model/prompt versions.

**Tradeoff:** users still need a downstream reasoning step for concise summaries/topics.

**Future rule:** derived context should reference exact pack/member inputs and remain separable from source evidence.

## D11 — record tool versions, do not pretend remote rebuilds are deterministic

**Decision:** preserve tool version lines and member hashes for each completed pack.

**Why:** YouTube and tools change. The same URL later may yield different bytes.

**Tradeoff:** there is no promise of bit-identical reacquisition.

**Operational consequence:** preserve important verified packs rather than treating the URL as sufficient evidence.

## D12 — keep downstream execution separate

**Decision:** ReasonPack does not choose or invoke an AI executor.

**Why:** context should remain reusable when model/provider selection changes.

**Tradeoff:** one more explicit handoff step exists today.

**Strategic consequence:** an Execution Packet can govern a particular job without redefining the source artifact.
