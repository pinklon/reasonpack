# GhostMesh ReasonPack durable acquisition supervisor v0.9

Status: isolated source-only candidate. No live ReasonPack, Gmail, Slack, worker or Production process was changed.

## Problem and operating principle

The old `ops/ghostmesh-reasonpack-intake.py::process_one` runs one blocking subprocess with `timeout=7200`. That is a two-hour total *worker* runtime limit, not a healthy-progress policy. Multi-hour video acquisition or normalization can legitimately exceed it.

A full mission needs **no arbitrary total duration cutoff**, while retaining finite per-step resources, cancellation, progress/readback and externally reviewed worker execution authority. A supervisor must not equate silence with failure or execute an unreviewed job twice when delivery/result state is unknown.

## Implemented source-only executable boundary

`ops/acquisition-supervisor.py` offers the following small, manually invoked development contract:

```bash
# Only after mail-gateway verification: use an existing signer-generated receipt
# and its originating HMAC-signed canonical gateway envelope.
REASONPACK_MAIL_INGEST_KEY=... python3 ops/acquisition-supervisor.py register \
  --admission /protected/admitted-job.json \
  --envelope /protected/signed-envelope.json \
  --allow-sender owner@example.org \
  --root /protected/isolated-acquisition-jobs

# Development-only, runs a fixed synthetic worker and absolutely no YouTube call.
python3 ops/acquisition-supervisor.py launch-fixture \
  --job /protected/isolated-acquisition-jobs/JOBID --ticks 10 --period-ms 200

# Restart-independent readback from an entirely new process:
python3 ops/acquisition-supervisor.py status --job /protected/isolated-acquisition-jobs/JOBID
```

The registration validates the same signed gateway envelope and sender allowlist as `mail-reasonpack.py`, re-derives message/video/job identities and canonical intent fingerprint and rejects receipts that do not exactly match. Do not share the signing key with a future model worker.

The launcher is deliberately hard-wired to the repository's `ops/acquisition-synthetic-worker.py`. It cannot execute caller-supplied commands or real video retrieval. Before starting work, a private pipe gate holds the child while the parent durably records the exact Linux process ID and `/proc/PID/stat` start ticks. This distinguishes the worker from later PID reuse.

The worker runs in its own process session, writes timestamped self-reported progress and a terminal synthetic completion marker. Supervisory readback is available from a fresh process after the original launcher exits. There is **no global mission timeout** in this path. If PID identity disappears without a corresponding coherent terminal record, status becomes `reconciliation-required-no-auto-retry` and no automatic replacement worker is dispatched.

The progress file is explicitly **worker-self-report, not independent witness evidence**. A matching synthetic completion marker is not independent authentication of actual YouTube retrieval, valid media, model usage or Gmail send. The supervisor always reports `production_acquisition_qualified=false`, `independent_completion_attested=false`, no dispatched email and provider costs UNKNOWN.

## Production commissioning gates

- **Do not** replace the active intake by editing a runtime release or toggling a systemd pointer. This source code does not invoke the current real downloader at all.
- Next implement a separately reviewed, fixed-path production backend adaptor with minimal credentials, durable bounded step claims, heartbeat/progress witnesses, cancellation, source-pack SHA validation, and crash-safe process adoption. Do not pass arbitrary user-provided CLI shell commands.
- Handle worker failure, process crash, provider timeout, interrupted delivery, partial output and restart/reconciliation without automatically replaying uncertain work. Account for no-progress observations with UNKNOWN, not fabricated percent completion or a global kill clock.
- The old 7,200-second blocking intake remains deployed/unchanged. Unattended processing of real three-hour video is **not** qualified by the synthetic supervisor.
- Preserve current Gmail source custody, single journal/poller owner and witnessed provider send contracts in Collab issues #86/#117. Future mission runtime telemetry should consume these verified measurements without inventing tokens, billing or customer charges.
- Reconcile source ancestry #3 → #4 → #6 → #7 → #9 → this source-only change before merge. Exact-head CI, independent review, installed release pin, owner-canary and rollback are separate gates.

## Test evidence

`python3 tests/test-acquisition-supervisor.py` executes a real synthetic child process and separately invoked supervisor commands. Positive and adversarial tests cover signed envelope binding, source substitution, privilege forgery, idempotency, fresh-launch gating, process identity, restart-readback, self-reported progress, clean completion, loss of a worker with UNKNOWN/reconciliation and refusal of automatic repeat dispatch.

No live email, Slack message, YouTube download, model call, payment, public Reader or Production mutation is made by these tests.

## Independent review hardening

Initial independent read-only review of this implementation found two P2 defects. A zombie could retain the same \`/proc/PID/stat\` start ticks after exit, and a crash between directory creation and the two registration writes could leave an unrecoverable partial job. Both are repaired before review promotion.

The supervisor now checks process state alongside PID/start ticks, excluding Z/X/x. Registration builds both private exact receipts in a sibling directory, fsyncs them, atomically renames into the canonical job name, then fsyncs the queue directory; crash before publication leaves no partial canonical job. Focused regressions cover zombies and interruption before publication, with successful retry after the simulated failure.

The worker's heartbeat and terminal marker remain **self-reported synthetic evidence**, not independent provider or acquisition attestation.

## Launch-intent failure recovery

The second read-only review found one remaining P2: interrupted log creation or Popen could strand a job that still looked unattempted. The launcher now durably publishes \`launch-intent-uncertain\` and increments the attempt counter **before any log or worker side effect**. A failed spawn, process interruption or log collision is reported as \`reconciliation-required-launch-uncertain\`. No automatic retry of this uncertain attempt is allowed. Separate negative tests inject Popen failure and a preexisting log file to prove the invariant.
