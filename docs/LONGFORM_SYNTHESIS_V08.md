# ReasonPack long-form synthesis v0.8

Status: source-only, non-Production. No model provider is invoked; no email is sent; no customer billing or public publication.

## Problem addressed

PR #7 stages immutable, source-bound observations for each long-form transcript segment. It intentionally refuses to render a whole-video assessment before all segments have been reconciled. This PR adds an offline binary synthesis tree and verifiable, hash-bound coverage receipt.

## Contract

1. `ops/longform-synthesis.py init --composition DIR --results DIR --synthesis DIR` requires every exact segment candidate in PR #7. It creates an immutable binary reduction tree, no fixed count of segments or video-duration limit.
2. `prepare --node level-001-node-000000` emits the exact child-bound research prompt and a strict per-node JSON output schema. It only becomes eligible after its child candidates exist. It calls no model.
3. A separately qualified, read-only model executor may produce `ghostmesh.reasonpack.synthesis-node.v1`. `stage --node ... --candidate FILE` verifies exact source/prompt/children, bounded observations and no authority to attest truth or publish. Staging is private and immutable, with no-overwrite atomic publication.
4. Continue level by level. Each higher node takes only at most two bounded lower-node observation records. The reduction depth grows logarithmically with the segment count, so hours-long transcripts do not need one giant model context.
5. `seal` requires every node to be present. It recursively revalidates exact bytes and child chains, rejects extra results, produces `coverage-receipt.json` and a separate bounded `whole-video-model-input.json` grounded in the root of the coverage tree.
6. `verify` checks the complete chain and final prompt digest.
7. `research-composer.py validate` and `reader-pipeline.py analysis` accept the final analysis only with a verified segmented synthesis directory, composition receipt and segment-results directory. The validation receipt links the whole-video analysis digest to the all-segment coverage receipt.

## Honest claims and mission telemetry

- `segments_covered` is deterministic input **coverage**, not semantic understanding or factual proof.
- Every node and the finished coverage receipt retain `semantic_review=NOT_ATTESTED` and no sending/publication authority.
- The final GhostMesh thesis is still model-authored interpretation, not a direct Tony statement or a verified experimental result.
- A separate independent claim-evidence assessment and owner-only delivered Gmail canary are required before authorizing unattended delivery.
- This PR creates no new telemetry/journal writer. Existing Collab #86/#117/#119 remain the sole source of truth for observed usage, charges and witnessed send acceptance.
- The legacy acquisition subprocess timeout remains in the old intake and is tracked under ReasonPack #8; this source-only improvement does not qualify uninterrupted multi-hour Production acquisition.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/test-longform-synthesis.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test-longform-segments.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test-reader-pipeline.py
./bin/reasonpack self-test
```

Fixtures prove a multi-level reduction tree, absence of missing leaf segments, exact-root coverage, altered prompt/leaf/node rejection, out-of-order preparation refusal, idempotent replay and output authority denial. Test code does NOT invoke a real model or claim scientifically valid synthesized conclusions.

**Rollback:** discard source worktree/branch. Running GhostMesh Gmail and ReasonPack services are unchanged.
