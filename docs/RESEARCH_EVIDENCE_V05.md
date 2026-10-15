# GhostMesh ReasonPack Research Evidence v0.5

Source state: locally committed feature branch candidate, not deployed. Mail dispatch and public publishing remain disabled.

## Why this increment matters

A machine-generated claim cannot be treated as independently supported merely because it includes an HTTPS citation. Every citation in a supported, partially supported, or disputed claim must match a collected research record tied to the exact verified video source. This check provides evidence traceability, not semantic truth.

## Research handoff

1. Run the canonical ReasonPack verifier and create the editorial input from a verified source.
2. An independently authorized research retrieval system collects public sources and records their identity, publisher, retrieval timestamp, evidence type, exact excerpt and SHA-256. The evidence register is bound to the canonical manifest SHA-256 and transcript SHA-256.
3. Run the `evidence` transition on the local workflow to lock the research record and validate source custody.
4. Run the `compose` command to create a bounded research prompt and strict JSON output schema in `composition/`. This stage explicitly does not invoke a model.
5. A separately qualified model with read-only permissions produces candidate JSON. `research-composer.py validate` checks source identity, valid registered URLs, and public SharePlane citation identities. It expressly records semantic review as NOT_ATTESTED.
6. The existing `analysis`, `render`, and `draft` stages prepare a private draft without sending it.

Workflow states:

`admitted -> source-verified -> awaiting-research -> research-evidence-verified -> analysis-unreviewed -> reader-private-draft -> email-private-draft`

## Tools

- `ops/research-evidence.py` verifies a supplied register and optionally binds an analysis against it.
- `ops/research-composer.py prepare --packet PATH --registry PATH --out DIR` creates a model prompt, strict analysis JSON schema and no-invocation receipt.
- `ops/research-composer.py validate --packet PATH --registry PATH --candidate PATH --out PATH` emits a limited validation receipt.
- `ops/reader-pipeline.py evidence --job JOB --registry PATH` admits a pinned source register.
- `ops/reader-pipeline.py compose --job JOB` emits a bounded model invocation input with a 180 KB ceiling.
- `ops/reader-pipeline.py analysis --job JOB --analysis PATH` requires the previously generated exact prompt/schema and rejects output citing unregistered sources or fabricated SharePlane publications.

## Security and authorization

Incoming mail is authenticated by the existing public Gmail responder. HMAC signing occurs only after admission, not as a replacement for it. Never share the signing secret with a public model or a recipient. No new Gmail routes, Cloudflare routes, service units, credentials or production environments are modified by this increment.

One submitted video creates one job. Model outputs and internet excerpts remain untrusted. Registered evidence is not the same as independently accepted support. The current Reader is a PRIVATE DRAFT with no public URL. There is no automatic final human review, Gmail send, or authorized web publication.

## Missing production gates

- Implement and qualify independent research source retrieval and bounded model runtime.
- Preserve exactly-once journal ownership and Gmail thread identity at the existing mail responder handoff.
- Require editorial corroboration before any user-visible claims are treated as verified.
- Owner-only Gmail canary with actual delivered receipt and rollback.
- Owner-controlled public release only after exact content digest approval.

## Verification

Run the offline tests:
```
python3 tests/test-reader-edition.py
python3 tests/test-mail-gateway-adapter.py
python3 tests/test-reader-pipeline.py
python3 tests/test-research-composition.py
./bin/reasonpack self-test
./tests/test-package.sh
```

The synthetic test media is not independent proof of any YouTube video. Passing simulated tests does not qualify Production email or public publication.

Rollback: stop using the isolated branch/worktree. The current live mail responder remains unchanged.
