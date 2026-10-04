# Slack ReasonPack Intake

## Purpose

Turn a YouTube URL posted to the GhostMesh Slack inbox into a durable ReasonPack job without making Slack an authority or storage system.

## Flow

```text
Slack #ghostmesh-inbox
        |
        v
signed Slack Events ingress
        |
        v
GhostMesh collaboration ledger (canonical event)
        |
        v
ReasonPack intake daemon
        |
        +--> ReasonPack evidence package
        |    /srv/ghostmesh/workspaces/artifacts/reasonpack/
        |
        +--> intake receipt
        |    /srv/ghostmesh/workspaces/state/reasonpack/receipts/
        |
        +--> queued Slack thread receipt
```

## Authority boundary

Slack carries intent and source coordinates. It does not grant Production or execution authority outside this bounded evidence-building action.

The worker consumes only canonical events in `collab:inbox`, validates YouTube URLs, deduplicates by canonical event plus URL, and records processing state independently.

## Runtime

Source:

- `ops/ghostmesh-reasonpack-intake.py`
- `ops/ghostmesh-reasonpack-intake-watchdog.sh`

Deployed runtime:

- `~/.local/bin/ghostmesh-reasonpack-intake`
- `~/.local/bin/ghostmesh-reasonpack-intake-watchdog.sh`

State:

- `/srv/ghostmesh/workspaces/state/reasonpack/intake.sqlite3`
- `/srv/ghostmesh/workspaces/state/reasonpack/receipts/`

Artifacts:

- `/srv/ghostmesh/workspaces/artifacts/reasonpack/`

The watchdog is registered with cron at boot and every minute. The worker itself polls the canonical ledger every five seconds.

## Slack outbound

If `SLACK_BOT_TOKEN` is present in the collaboration runtime environment, pending completion/failure receipts are delivered to the originating Slack thread.

If the token is absent, the receipt remains `pending` in the intake database. Adding the credential later does not lose prior completion messages.

The ChatGPT Slack connector credential is deliberately not reused.

## YouTube acquisition

The VPS ReasonPack runtime includes:

- yt-dlp
- yt-dlp EJS support
- Node 22
- ffmpeg / ffprobe
- bgutil PO-token provider

The October 4, 2026 live qualification showed YouTube returning `LOGIN_REQUIRED` / "Sign in to confirm you're not a bot" to both the Hostinger IPv4 and IPv6 egress before media acquisition.

The worker classifies that condition as `blocked_youtube_ip`, retains the job and diagnostic receipt, and does not loop on retries.

Preferred remediation is a bounded non-datacenter acquisition path, such as owner-controlled residential egress. Do not copy a primary browser cookie database to the VPS.

## Qualification

Run:

```bash
python3 tests/test-slack-intake.py
bash tests/test-package.sh
reasonpack self-test
reasonpack doctor
```

A live smoke test should additionally prove:

1. Slack message ingests into `collab:inbox`.
2. Slack link markup normalizes to the exact YouTube URL.
3. One canonical event creates one job.
4. One job creates one ReasonPack or one bounded failure receipt.
5. A configured outbound bot posts exactly one thread receipt.
