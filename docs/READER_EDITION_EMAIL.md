# GhostMesh ReasonPack Reader + Email Handoff v0.3

State: source candidate, not commissioned. No live GhostMesh email listener, service symlink, production site, or public route was modified.

## Product

An authorized correspondent emails a YouTube link requesting a ReasonPack. The eventual delivery should contain a short executive verdict and an elegant full Reader Edition with three visibly separated intellectual layers:

1. What the video said, with timestamped quotes/claims and creator attribution.
2. What independent evidence establishes, including uncertainties, counterevidence and source links.
3. An original GhostMesh thesis based on public, appropriately attributed and revision-pinned SharePlane Works. This is GhostMesh editorial, never automatically represented as Tony Malott's authored Work or personal endorsement.

The canonical ReasonPack keeps the media, transcript, metadata and integrity receipt. Analysis and publications are derivatives outside that directory.

## Implemented programs

ops/mail-reasonpack.py admit
- Accepts a canonical JSON envelope authenticated by HMAC-SHA256 via REASONPACK_MAIL_INGEST_KEY, intended for the existing verified GhostMesh mail gateway.
- Independently checks the verified-sender allowlist, gateway admission flags, message ID, recency, one explicit fresh ReasonPack request, one distinct valid YouTube ID.
- Produces idempotent restricted 0600 job receipts. Cannot acquire video, invoke models, send email, or publish.

ops/editorial-packet.py
- Independently runs the canonical source verifier.
- Preserves transcript hash, source manifest hash, transcript provenance, untrusted transcript and optionally public owner-reviewed pinned Work excerpts.
- Produces an input packet for an authorized read-only research executor; no model or network calls.

ops/reader-edition.py
- Requires a valid canonical source pack and versioned analysis JSON.
- Validates source ID, primary-source citation links, timestamps, verdicts, SharePlane URL host, pinned source revisions.
- Escapes all model-controlled HTML fields, restricts external links to HTTPS, has no active script and a strict CSP. Mobile responsive; print layout.
- Produces standalone index.html and reader-receipt.json in a separate versioned folder, with SHA256 evidence hashes and private-draft status. Never publishes.

ops/mail-reasonpack.py draft
- Validates admitted request, video identity, analysis/HTML digest match.
- Prepares a reply-threaded RFC MIME .eml draft with Reader Edition HTML attachment, plain-text verdict and separate original GhostMesh thesis.
- Cannot dispatch email.

## Analysis input schema

Root schema: ghostmesh.reasonpack.analysis.v1.

Required:
- video_id, headline, deck, executive, source_account, evidence_summary
- claims: 1 to 30 records with timestamp (MM:SS or HH:MM:SS), statement, assessment, verdict, sources [{label,url}]
- accepted verdicts: supported, partially-supported, unsupported, disputed, unknown
- supported claims require at least one external source reference, but evidence corroboration is still a separate review gate
- thesis: title, argument, mechanism, counterargument, implication
- shareplane_works: optional records with title, canonical public URL, source_commit

Explicit byline: GhostMesh Editorial. Pinned public owner-authored Works may inform this editorial but do not establish owner approval of the newly generated thesis.

## Sample offline run

From the isolated repository worktree:

    ./bin/reasonpack verify examples/sample-reasonpack
    python3 ops/editorial-packet.py --pack examples/sample-reasonpack --out /tmp/reasonpack-editorial-packet.json
    python3 ops/reader-edition.py --pack examples/sample-reasonpack --analysis examples/reader-synthetic-analysis.json --out /tmp/reasonpack-reader-sample --allow-fixture

The fixture is synthetic. Never publish it as an analysis of an actual source.

When integrating live email, the mail responder must first validate the incoming provider headers and envelope identity, then HMAC-sign the canonical normalized payload. Signed arbitrary user-supplied assertions are not evidence of genuine DMARC/SPF/DKIM alignment.

## Required before any Production delivery

1. Integrate with the current mail responder, without replacing production binaries or restarting unrelated services. Restrict the existing mail ingestion key to the authenticated gateway and explicitly qualified admission verifiers; never pass it to model or acquisition subprocesses.
2. Implement bounded independent model-assisted claim research, with allowed external resources, timeouts, budgets, provenance, honest HOLD on failures, and an exact analysis JSON contract.
3. Independently review factual support and thesis attribution; defend against prompt injection from incoming mail, transcript and retrieved sites.
4. Perform owner-only email canary with exact source, generated edition and same-thread reply verification. Enforce exactly-once delivery and test rollback.
5. For external correspondents, require consent, rate/abuse limits and recipient-bound private access controls with expiry/revocation.
6. Owner approval of an exact release digest is mandatory before any public static publication. Readers are not SharePlane Works and must not affect its article count.

## Security / operational state

The implementation has NO email sending, public URL issuance, user permission changes, credential operations, timer/service modifications, or production dispatch. All generated content is private draft. Stop using it by removing the staged job; the active mail responder remains unchanged.

Local tests: python3 tests/test-reader-edition.py; existing package tests and source verifier.
Tests passing does NOT imply deployed or commissioned.

## Verified integration point in the currently active mail release (read-only inspection)

The deployed GhostMesh mail package has the authenticated public email entrypoint at integrations/gmail/gm_public_responder.py. The existing validate_public_email() routine verifies sender alignment (DMARC or aligned DKIM), recipient identity, non-bulk/non-automated status, plain-text size, spam state and owner identity where relevant. process_message() then applies admission, deterministic eligibility, durable journal reservation, context/disclosure fencing, tool-free reasoning and exactly-once reply handling.

The existing gm_intake.py is explicitly a correspondence-only owner verifier: operational mail admission is forbidden. Do not alter that invariant to enable ReasonPack. A future ReasonPack adapter belongs AFTER public mail verification and sender-policy admission and MUST preserve journal reservation, retry budget, thread identity, loop defenses and disclosure policy. It should sign a normalized bounded request for a new reasoned-content service, not grant deployment privileges. The same inbound message must not also trigger the ordinary response path while pending asynchronous analysis.

Before integration, compare the specific source release used for the patch to live mail-current and independently verify exact-head tests. Do not edit or restart immutable live releases.

## New v0.4 local orchestrator and gateway handoff

- ops/reader-pipeline.py adds monotonic, receipt-backed, locked transitions: admitted → source-verified → awaiting-research → research-evidence-verified → analysis-unreviewed → reader-private-draft → email-private-draft. Initialization rechecks the signed gateway envelope and explicit sender allowlist using the acquisition supervisor's existing source verifier. It checks source hashes on every downstream transition, creates only local files, and never sends.
- ops/mail-gateway-adapter.py is an import-only, owner-only canary helper. It may sign a verified Gmail envelope *only after* the live responder has independently authenticated and admitted the sender. It preserves Gmail message and thread IDs and does not authenticate any incoming email itself. Key access must remain restricted to that boundary.
- Public owner-authored thesis context is restricted to versioned files committed under editorial/approved-works. Their source Git revision and source blob identity are carried as metadata. This does not make model-generated text author-approved. Public route reachability has not been verified; do not advertise any URL as accessible until probed.
- CI now runs gateway-adapter and synthetic full-lifecycle tests. The synthetic pack is structurally hash-valid for testing but NOT an actual acquired YouTube video; production requires independent acquisition custody and live-source evidence.

## Essential next boundary

The deployed Gmail responder currently reserves each email in its durable journal, then produces one immediate model decision and may send a reply. A ReasonPack request must diverge **after authentication, policy admission, and journal reservation**, so the ordinary responder cannot also send. The asynchronous job needs an explicit durable claim and a separate qualified final-delivery path. Blindly dispatching a second reply against the same journal key risks duplicate or lost email. Do not activate this bridge until the exact-head mail release and independently reviewed tests prove that handoff.

## Operator-only owner-canary runbook (NOT yet a live send)

The mail gateway signer, installed reasoner and Gmail dispatcher have NOT been connected by this branch. An operator can exercise a previously admitted job without changing the live responder:

The trusted `init` verifier needs the existing `REASONPACK_MAIL_INGEST_KEY` to check the signed envelope. The source code removes that key from subsequent subprocess environments. Key access and isolation still require separate installed-runtime qualification.

```bash
python3 ops/reader-pipeline.py init --admission /protected/verified-request-receipt.json --envelope /protected/signed-gateway-envelope.json --allow-sender owner@example.org --root /protected/reader-jobs
python3 ops/reader-pipeline.py source --job /protected/reader-jobs/JOBID --pack /protected/verified-source-pack
python3 ops/reader-pipeline.py research --job /protected/reader-jobs/JOBID
# The registry lists separately collected evidence. A URL or registry entry does not
# establish claim truth; the captured-source path also requires --capture-dir and --catalog.
python3 ops/reader-pipeline.py evidence --job /protected/reader-jobs/JOBID --registry /protected/research-sources.json
python3 ops/reader-pipeline.py compose --job /protected/reader-jobs/JOBID
# A separately authorized researcher must evaluate the actual video and sources and
# write analysis-v1.json. The composition step only prepares context; it invokes no model.
python3 ops/reader-pipeline.py analysis --job /protected/reader-jobs/JOBID --analysis /protected/analysis-v1.json
python3 ops/reader-pipeline.py render --job /protected/reader-jobs/JOBID
python3 ops/reader-pipeline.py draft --job /protected/reader-jobs/JOBID --from-email ghostmesh@malott.ai
python3 ops/reader-pipeline.py status --job /protected/reader-jobs/JOBID
```

STOP at email-private-draft. Sending through the Gmail API is not supported by this feature and cannot be inferred from passing tests. Do not provide a public Reader URL or claim author signoff. The next deployment decision is a **separate** exact-head patch and independent review of the active Gmail responder, with its durable journal and reply state-machine behavior preserved.

Rollback: discard the isolated worktree/branch or discontinue the canary job. The current Production releases, credentials, systemd units, and source packages remain untouched.
