#!/usr/bin/env python3
"""GhostMesh Slack -> ReasonPack intake worker.

Consumes canonical GhostMesh collaboration events from collab:inbox.
Slack remains a surface; the canonical collaboration ledger is the trigger source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from urllib import request

DEFAULT_COLLAB_DB = "/srv/ghostmesh/workspaces/state/ghostmesh-collab/collab.sqlite3"
DEFAULT_STATE_DB = "/srv/ghostmesh/workspaces/state/reasonpack/intake.sqlite3"
DEFAULT_OUTPUT_ROOT = "/srv/ghostmesh/workspaces/artifacts/reasonpack"
DEFAULT_REASONPACK = "/home/ghostmesh/.local/bin/reasonpack"
YOUTUBE_RE = re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/[^\s<>|]+", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_url(raw: str) -> str:
    return raw.rstrip(".,;:!?)]}'\"")


def youtube_urls(text: str) -> list[str]:
    out: list[str] = []
    for match in YOUTUBE_RE.finditer(text or ""):
        url = normalize_url(match.group(0))
        if url not in out:
            out.append(url)
    return out


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS jobs (
            job_key TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            source_seq INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            slack_channel TEXT,
            slack_thread_ts TEXT,
            status TEXT NOT NULL,
            artifact_path TEXT,
            receipt_path TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deliveries (
            job_key TEXT PRIMARY KEY,
            slack_channel TEXT NOT NULL,
            slack_thread_ts TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    con.commit()
    return con


def read_new_events(collab_db: Path, state: sqlite3.Connection) -> list[sqlite3.Row]:
    known = {r["event_id"] for r in state.execute("SELECT DISTINCT event_id FROM jobs")}
    uri = f"file:{collab_db}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=30) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT seq,event_id,actor_id,space_id,thread_id,event_type,text,
                   surface,surface_event_id,metadata_json
            FROM events
            WHERE space_id='collab:inbox' AND event_type='message'
            ORDER BY seq
            """
        ).fetchall()
    return [r for r in rows if r["event_id"] not in known]


def slack_coords(row: sqlite3.Row) -> tuple[str | None, str | None]:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
        slack = metadata.get("slack") or {}
        return slack.get("channel"), slack.get("thread_ts") or slack.get("ts")
    except Exception:
        return None, None


def create_jobs(state: sqlite3.Connection, rows: list[sqlite3.Row], allowed_actors: set[str]) -> int:
    created = 0
    for row in rows:
        if row["actor_id"] not in allowed_actors:
            key = f'{row["event_id"]}:ignored-actor'
            now = utc_now()
            channel, thread_ts = slack_coords(row)
            state.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_key,event_id,source_seq,source_url,slack_channel,slack_thread_ts,
                    status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?, ?,?)""",
                (key, row["event_id"], row["seq"], "", channel, thread_ts, "ignored_actor", now, now),
            )
            continue
        urls = youtube_urls(row["text"])
        channel, thread_ts = slack_coords(row)
        if not urls:
            # Mark a no-op event so it is not scanned forever.
            key = f'{row["event_id"]}:noop'
            now = utc_now()
            state.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_key,event_id,source_seq,source_url,slack_channel,slack_thread_ts,
                    status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?, ?,?)""",
                (key, row["event_id"], row["seq"], "", channel, thread_ts, "ignored_no_youtube", now, now),
            )
            continue
        for url in urls:
            key = hashlib.sha256(f'{row["event_id"]}\0{url}'.encode()).hexdigest()
            now = utc_now()
            cur = state.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_key,event_id,source_seq,source_url,slack_channel,slack_thread_ts,
                    status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?, ?,?)""",
                (key, row["event_id"], row["seq"], url, channel, thread_ts, "queued", now, now),
            )
            created += cur.rowcount
    state.commit()
    return created


def classify_failure(stderr: str) -> str:
    s = stderr.lower()
    if "sign in to confirm you" in s and "not a bot" in s:
        return "blocked_youtube_ip"
    if "private video" in s or "members-only" in s or "login required" in s:
        return "blocked_auth_required"
    if "unsupported url" in s:
        return "rejected_url"
    return "failed"


def receipt_for(job: sqlite3.Row, status: str, output: Path | None, error: str | None) -> dict:
    receipt: dict = {
        "schema": "ghostmesh-reasonpack-intake-receipt.v1",
        "job_key": job["job_key"],
        "source_event_id": job["event_id"],
        "source_seq": job["source_seq"],
        "source_url": job["source_url"],
        "status": status,
        "completed_at": utc_now(),
    }
    if output:
        receipt["artifact_path"] = str(output)
        manifest = output / "manifest.json"
        transcript = output / "transcript.txt"
        source = output / "source.json"
        if manifest.exists():
            receipt["manifest_sha256"] = sha256_file(manifest)
        if transcript.exists():
            receipt["transcript_sha256"] = sha256_file(transcript)
        if source.exists():
            try:
                meta = json.loads(source.read_text())
                receipt["video_id"] = meta.get("id")
                receipt["title"] = meta.get("title")
                receipt["channel"] = meta.get("channel")
                receipt["duration_seconds"] = meta.get("duration")
            except Exception:
                pass
    if error:
        receipt["error"] = error[-4000:]
    return receipt


def queue_delivery(state: sqlite3.Connection, job: sqlite3.Row, body: str) -> None:
    if not job["slack_channel"] or not job["slack_thread_ts"]:
        return
    state.execute(
        """INSERT INTO deliveries(job_key,slack_channel,slack_thread_ts,body,status,updated_at)
           VALUES(?,?,?,?, 'pending',?)
           ON CONFLICT(job_key) DO UPDATE SET
             body=excluded.body,status='pending',last_error=NULL,updated_at=excluded.updated_at""",
        (job["job_key"], job["slack_channel"], job["slack_thread_ts"], body, utc_now()),
    )
    state.commit()


def format_delivery(receipt: dict) -> str:
    status = receipt["status"]
    title = receipt.get("title") or receipt.get("video_id") or "YouTube source"
    if status == "complete":
        return (
            f"*ReasonPack complete*\n"
            f"{title}\n"
            f"VPS: `{receipt['artifact_path']}`\n"
            f"Manifest SHA-256: `{receipt.get('manifest_sha256','unknown')}`\n"
            f"Transcript SHA-256: `{receipt.get('transcript_sha256','unknown')}`"
        )
    if status == "blocked_youtube_ip":
        return (
            "*ReasonPack captured, acquisition blocked by YouTube*\n"
            "The VPS egress IP received YouTube's bot/login challenge. "
            "The job is retained and will not be hammered with retries. "
            "GhostMesh intake and provenance are intact."
        )
    return f"*ReasonPack failed*\nStatus: `{status}`\nThe job and diagnostic receipt are retained on the VPS."


def process_one(
    state: sqlite3.Connection,
    job: sqlite3.Row,
    reasonpack: Path,
    output_root: Path,
    receipt_root: Path,
) -> None:
    now = utc_now()
    state.execute(
        "UPDATE jobs SET status='running',attempts=attempts+1,updated_at=? WHERE job_key=?",
        (now, job["job_key"]),
    )
    state.commit()
    env = os.environ.copy()
    env["PATH"] = f"/home/ghostmesh/.local/bin:{env.get('PATH','')}"
    env["REASONPACK_ROOT"] = str(output_root)
    try:
        proc = subprocess.run(
            [str(reasonpack), job["source_url"], str(output_root)],
            text=True,
            capture_output=True,
            timeout=7200,
            env=env,
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        if proc.returncode == 0:
            candidates = [Path(line.strip()) for line in (proc.stdout or "").splitlines() if line.strip().startswith("/")]
            output = candidates[-1] if candidates else None
            if output is None or not (output / "manifest.json").exists():
                raise RuntimeError("ReasonPack returned success without a verifiable artifact path")
            status, error = "complete", None
        else:
            output = None
            status, error = classify_failure(proc.stderr or combined), combined
    except subprocess.TimeoutExpired as exc:
        output = None
        status, error = "failed_timeout", str(exc)
    except Exception as exc:
        output = None
        status, error = "failed_worker", f"{type(exc).__name__}: {exc}"

    receipt = receipt_for(job, status, output, error)
    receipt_root.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_root / f'{job["job_key"]}.json'
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    state.execute(
        """UPDATE jobs SET status=?,artifact_path=?,receipt_path=?,error=?,updated_at=?
           WHERE job_key=?""",
        (status, str(output) if output else None, str(receipt_path), error[-4000:] if error else None, utc_now(), job["job_key"]),
    )
    state.commit()
    queue_delivery(state, job, format_delivery(receipt))


def post_slack(token: str, channel: str, thread_ts: str, body: str) -> None:
    payload = json.dumps({"channel": channel, "thread_ts": thread_ts, "text": body}).encode()
    req = request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode())
    if not result.get("ok"):
        raise RuntimeError(f"Slack chat.postMessage failed: {result.get('error','unknown_error')}")


def drain_deliveries(state: sqlite3.Connection) -> int:
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        return 0
    sent = 0
    rows = state.execute("SELECT * FROM deliveries WHERE status='pending' ORDER BY updated_at LIMIT 20").fetchall()
    for row in rows:
        try:
            post_slack(token, row["slack_channel"], row["slack_thread_ts"], row["body"])
            state.execute(
                "UPDATE deliveries SET status='sent',attempts=attempts+1,last_error=NULL,updated_at=? WHERE job_key=?",
                (utc_now(), row["job_key"]),
            )
            sent += 1
        except Exception as exc:
            state.execute(
                "UPDATE deliveries SET attempts=attempts+1,last_error=?,updated_at=? WHERE job_key=?",
                (f"{type(exc).__name__}: {exc}"[-2000:], utc_now(), row["job_key"]),
            )
    state.commit()
    return sent


def run_once(args: argparse.Namespace) -> dict:
    state = open_state(Path(args.state_db))
    events = read_new_events(Path(args.collab_db), state)
    allowed_actors = {x.strip() for x in args.allowed_actors.split(",") if x.strip()}
    created = create_jobs(state, events, allowed_actors)
    pending = state.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY source_seq,created_at").fetchall()
    processed = 0
    for job in pending:
        process_one(
            state,
            job,
            Path(args.reasonpack),
            Path(args.output_root),
            Path(args.receipt_root),
        )
        processed += 1
    sent = drain_deliveries(state)
    counts = {r["status"]: r["n"] for r in state.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status")}
    return {"created": created, "processed": processed, "deliveries_sent": sent, "status_counts": counts}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--collab-db", default=os.environ.get("GM_COLLAB_DB", DEFAULT_COLLAB_DB))
    p.add_argument("--state-db", default=os.environ.get("REASONPACK_INTAKE_DB", DEFAULT_STATE_DB))
    p.add_argument("--output-root", default=os.environ.get("REASONPACK_ROOT", DEFAULT_OUTPUT_ROOT))
    p.add_argument("--receipt-root", default=os.environ.get("REASONPACK_RECEIPT_ROOT", "/srv/ghostmesh/workspaces/state/reasonpack/receipts"))
    p.add_argument("--reasonpack", default=os.environ.get("REASONPACK_BIN", DEFAULT_REASONPACK))
    p.add_argument("--poll-seconds", type=int, default=int(os.environ.get("REASONPACK_POLL_SECONDS", "5")))
    p.add_argument("--allowed-actors", default=os.environ.get("REASONPACK_ALLOWED_ACTORS", "person:tony"))
    p.add_argument("--daemon", action="store_true")
    args = p.parse_args()
    if not args.daemon:
        print(json.dumps(run_once(args), sort_keys=True))
        return 0
    while True:
        try:
            result = run_once(args)
            if result["created"] or result["processed"] or result["deliveries_sent"]:
                print(json.dumps({"at": utc_now(), **result}, sort_keys=True), flush=True)
        except Exception as exc:
            print(json.dumps({"at": utc_now(), "error": f"{type(exc).__name__}: {exc}"}), flush=True)
        time.sleep(max(2, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
