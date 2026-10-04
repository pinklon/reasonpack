# Feature Posture — Quick Reference

Use this page when someone needs a one-screen answer.

## CURRENT

**Source:** one allowlisted YouTube URL; metadata/media/caption acquisition; no playlists.

**Transform:** H.264/AAC MP4, AAC audio, ffprobe metadata.

**Transcript:** source captions first; optional explicitly configured local Whisper fallback; transcript status always matters.

**Evidence:** member byte counts, SHA-256 hashes, manifest, independent checksum list, closed-directory verifier.

**Operations:** doctor, inspect, build, verify, self-test, quick `yt URL` flow.

**Platform:** macOS, Linux, Windows via WSL reference install paths.

**External side effects:** source acquisition only. No auto-upload, publication, telemetry or downstream AI execution.

## NEXT

Derived summaries/topics, timestamp/chapter index, keyframes, richer diagnostics, signed releases, batch intake, enterprise proxy guidance, native Windows, storage adapters, optional Execution Packet adapter.

## NOT YET

Knowledge graph, team sync service, remote registry as core dependency, background monitor, browser/private-account credential import, automatic AI-agent execution.

For full semantics and caveats, read `PRODUCT_FEATURE_SET.md`.
