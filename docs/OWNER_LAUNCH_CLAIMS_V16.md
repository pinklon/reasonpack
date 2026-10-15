# ReasonPack one-time owner launch claims, v0.16

STATUS: SOURCE ONLY. No root helper installed, no trusted signer commissioned, no video acquisition, email, model invocation or payment.

## Why

A valid signed acquisition grant is not automatically single use. The worker owns its job directory, so its supervision.json attempts counter cannot prevent a replay after failure, uncertain launch, or a malicious reset.

The reviewed systemd template now includes exactly one fixed owner-protected prestart command:

    ExecStartPre=+/usr/bin/python3 @IMMUTABLE_RELEASE_DIR@/ops/acquisition-owner-prestart.py --job-id %i

The plus prefix runs that fixed, immutable reviewed script as root before the normal ghostmesh worker. This is a new privileged capability and MUST have explicit owner/source review and a separately qualified immutable release. It has NOT been installed in the existing disabled PR #15 systemd unit.

## Trust and one-time consumption

The root prestart helper verifies (1) root effective UID, (2) execution only from exact immutable /opt/ghostmesh/reasonpack/releases/<commit> source, (3) the exact registered source admission and external Ed25519 signed grant from the authenticated Gmail writer, and (4) the pre-provisioned root-owned, mode 0600 SQLite ledger at /var/lib/ghostmesh/reasonpack/launch-claims.sqlite3.

It then opens a SQLite BEGIN IMMEDIATE transaction with synchronous=FULL. Unique job IDs, nonces and grant SHA-256 digests make the grant at most once, including across concurrent or repeated unit starts. It creates one root-owned readonly permit under /var/lib/ghostmesh/reasonpack/permits/<jobid>.json, fsyncs, and commits before systemd may launch the normal worker.

The non-root worker rechecks the signed grant and the exact root-owned permit BEFORE its downloader preflight. The existing Linux sealed-memfd admission handoff prevents mutable disk job records from switching the authorized video before the child starts.

The helper deliberately DOES NOT create the worker job's .lock file as root, since that would prevent the non-root worker opening the lock. SQLite is the owner authority; worker lock is still a local execution serializing mechanism.

A crash or IO error after recording a claim but before storing the permit requires manual owner reconciliation. The state must not be automatically cleared/retried. This is fail closed, with a potentially stranded job but no duplicate billing or downloader activation.

## Separate initialization and ownership

The helper's distinct --init-owner-ledger command is root-only, create-only and not used by the unit. It creates only a protected ledger schema and public permit structure; no signing keys or granting mechanism. Production paths and root custody are fixed.

The actual Gmail signer, its protected private key, the public signer registry, signing-issuance proof and the owner permit database remain uncommissioned. Only the existing Collab journal/transport writer may own the authorization issuance. No new poller/sender is authorized.

## Qualification

Unit and release-preflight contracts demand the exact immutable fixed prestart path. New offline tests cover concurrent one-claim racing, uniqueness of job ID/nonce/grant digest, replay after permit deletion, tampered permits, non-root refusal, and no other privileged unit commands. These source tests are not an actual systemd canary.

Remaining gates: independent exact-head code review and hosted CI, owner installation/rollback of a newly reviewed release, actual synthetic instance one-time/kill witness, trusted Gmail signer/journal handoff, isolated real video and semantic research, then exactly-once witnessed private Gmail Reader. The old PR #15 root-owned installed release and live Gmail service remain unchanged. There is no overall video length/time cap.
