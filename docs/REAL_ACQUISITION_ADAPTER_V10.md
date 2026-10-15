# ReasonPack fixed real acquisition adapter v0.10

Status: **source-only, operator-gated, no Production activation**. The real downloader was NOT invoked during qualification. All network-facing tests use a fake subprocess backend and structurally valid synthetic package fixture. This PR does not retire the old 7,200-second intake timeout in the installed daemon.

## Purpose

Continue ReasonPack issue #8 by adding an **exact code-pinned real backend** to the durable supervisor introduced by PR #10. Multi-hour video missions cannot depend on a single caller waiting with a two-hour global timeout. Each long-running acquisition is a separately owned process with durable registered job identity, one explicit launch, independent readback, and a source-verification boundary.

## Fixed backend implementation

- `ops/acquisition-real-worker.py` pins the reviewed installed ReasonPack implementation at `/home/ghostmesh/.local/share/reasonpack/reasonpack` and SHA-256 `3fb0e0b7b4eb0977671b12de9b28d9a41fa6f539a2b0ba6e426f6643238b6fef`.
- The source-only backend invokes **exactly** `reasonpack build https://www.youtube.com/watch?v=VIDEO_ID JOBDIR/raw-acquisition`. There is no arbitrary command, shell, destination or URL from user-controlled model output. Source URL derives from an already HMAC-verified admitted mail receipt.
- `acquisition-supervisor.py launch-real` requires an explicit `--permit-network-acquisition` flag **and** an operator-supplied copy of the exact reviewed backend digest; it otherwise refuses to spawn anything. It persists a launch-intent-uncertain receipt before creating log files or starting the child, then gates the child on recorded PID and proc start ticks.
- The worker passes a minimal fixed PATH, language and fresh private HOME/XDG config directory. It does not inherit the email signing key or operator environment credentials and has no mail-sending, billing, model, deployment or public publication path.
- It polls a subprocess within its process session without a total mission deadline. It writes private, self-reported file-presence/byte-count hints and a bounded log-resource guard. **Observed files are not verified source progress, and worker heartbeat is not independent witness proof.**
- A zero CLI exit is not sufficient for success. It requires the canonical ReasonPack package verifier, exact manifest source URL and source video ID, and nonempty video/audio/transcript files. The worker rechecks the CLI bytes before writing its self-reported result. The independent supervisor readback re-runs the verifier, checks the result against the registered job, and reports `source-package-reverified` only with matching manifest/transcript hashes. These checks validate pack consistency, not YouTube origin or factual assertions.
- Missing, altered, incomplete or uncertain output enters HOLD and is not automatically retried. A changed installed CLI hash also HOLDs. For real production use, root/owner release pinning, stage progress witnesses, per-operation resource controls, cancellation and integration into the existing journal are still required.

## Source-only preflight

A reviewer can inspect the existing installed backend without downloading anything:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import importlib.util
spec=importlib.util.spec_from_file_location('fixed_acquisition','ops/acquisition-real-worker.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(m.preflight())
PY
```

A future qualified operator may manually invoke `acquisition-supervisor.py launch-real --job JOB --permit-network-acquisition --expected-cli-sha256 PIN`, but **this PR does not grant permission to activate it in Production**. Keep the active Slack/Gmail intake and original mail release untouched. Do not assume YouTube access is possible without a provider IP/auth challenge, or attempt cookie/credential escalation.

## Qualification

- `tests/test-acquisition-real-worker.py` simulates an expected backend call, synthetic output, its independent structural verification, a source-ID mismatch, corrupted pack, missing media, code drift, nonzero backend return, explicit launch authorization and no ambient credential propagation.
- `tests/test-acquisition-supervisor.py` covers signed intake, PID identity, restart readback, process loss, spawn failure, zombie state, atomic registration, and real launch flag/digest refusals.
- Tests never use real YouTube network acquisition.
- Exact-head hosted CI and independent review required before merge. No service or timer can be switched solely from these tests.

## Remaining true milestones

1. Qualify the fixed backend in an isolated nonprod real-video trial with the owner authorizing **one** source; measure the actual network acquisition, transcode, source-custody bytes, resource use, and failure/readback.
2. Independently qualify bounded stage-level progress and cancellation/recovery for stalled operations. No arbitrary **video length** ceiling, but finite individual resource and failure budgets.
3. Integrate into the existing single Slack/Gmail intake journal under current source writer custody; do not create a second receiver and do not silently migrate legacy jobs.
4. Commission bounded inference and semantic-review pipeline; preserve existing Collab #86 and #117 telemetry/witness authority.
5. Owner-only email canary must witness one actual delivery, not just source-package completion.

Rollback: abandon this staged branch or leave the new command uninvoked. Active GhostMesh and ReasonPack daemons are unchanged.

## Independent review finding and exact source limitations

The first read-only security review of this candidate found that the real backend runs in its own process session. If the supervised worker is killed with SIGKILL, the downloader/transcoder group may survive, so worker PID loss alone cannot be equated to stopped acquisition. Source was hardened to include exact backend PID/start ticks and process group in worker self-reported progress. The supervisor's readback now reports \`orphaned-backend-active-reconciliation-required\` for an observed still-running backend and refuses an automatic replacement. A regression exercises the situation with a harmless independent sleep process and verifies no automatic kill or retry.

This observation is **not sufficient for Production process containment**. A compromised worker can forge self-report metadata, and active backend termination/release requires a separately reviewed cgroup or equivalent process-group/privilege boundary, an independent process witness and operator-approved cancellation. No autonomous orphan cleanup is implemented.

The installed ReasonPack CLI remains version \`1.0-refkit.1\`. Its embedded pack verifier uses whole-file reads, which can cause memory pressure for multi-gigabyte, multi-hour media, and its \`build\` sequence is not yet resumable step by step. Real multi-hour commissioning must therefore repair/qualify streaming checksum verification and per-stage restart support in the pinned CLI before relying on this adapter. The installed CLI digest in this source is a readback of the current executable, **not** an assertion that the CLI itself is production-qualified for long media.

The backend code, tests and README are source only. No real YouTube request was made during these tests; the worker is not installed or invoked by the live intake.
