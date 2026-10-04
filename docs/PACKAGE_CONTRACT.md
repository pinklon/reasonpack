# ReasonPack Package Contract

## Purpose

This document defines what a successful `ghostmesh-reasoning-pack-v1` directory means in the current reference runtime.

It is deliberately narrower than a general archival standard. The goal is a small, inspectable contract that a human or script can verify locally.

## Required members

| Member | Role | Required | Evidence expectation |
|---|---|---:|---|
| `video.mp4` | normalized visual/audio analysis copy | Yes | non-empty, size + SHA-256 tracked |
| `audio.m4a` | audio-only analysis member | Yes | non-empty, size + SHA-256 tracked |
| `transcript.txt` | text used for later reasoning | Yes | non-empty, provenance explained by transcript status |
| `transcript-status.json` | transcript provenance/status | Yes | source-captions or local-fallback semantics |
| `source.json` | yt-dlp source metadata | Yes | non-empty, exact bytes tracked |
| `ffprobe.json` | technical metadata for normalized video | Yes | non-empty, exact bytes tracked |
| `manifest.json` | member inventory and source/tool context | Yes | schema `ghostmesh-reasoning-pack-v1` |
| `SHA256SUMS.txt` | independent checksum list | Yes | includes manifest and tracked members |
| `captions.vtt` | original selected source caption file | Conditional | included when source captions are used |

## `manifest.json`

Current shape:

```json
{
  "schema": "ghostmesh-reasoning-pack-v1",
  "sourceUrl": "https://www.youtube.com/watch?v=...",
  "tools": {
    "yt-dlp": "...",
    "ffmpeg": "...",
    "ffprobe": "...",
    "python3": "..."
  },
  "members": [
    {
      "path": "video.mp4",
      "sha256": "<64 lowercase hex characters>",
      "bytes": 12345
    }
  ]
}
```

The manifest tracks content members. It does not claim copyright rights, factual correctness or downstream approval.

## Closed-directory rule

Verification computes the set:

```text
allowed regular files = manifest members + manifest.json + SHA256SUMS.txt
```

Any other regular file causes verification failure.

Why this matters: a pack should not quietly accumulate analyst notes, hidden outputs, model summaries, screenshots and scratch files until nobody knows what the manifest actually covers.

If you want to add derived work, use one of these patterns:

```text
Parent folder/
├── source-reasonpack/        # canonical verified pack
└── analysis/                 # derived work, not part of source pack
```

or create a separately versioned derived artifact with an explicit reference back to the pack/member hashes.

## Transcript status semantics

### Source captions

Typical record:

```json
{
  "status": "source-captions",
  "sourceFile": "captions.vtt"
}
```

Meaning: `transcript.txt` was simplified from source-provided/automatic YouTube caption material retained in the pack.

It does **not** mean captions are human-authored or error-free.

### Local Whisper fallback

Record includes:

- `status: local-whisper-fallback`;
- Whisper CLI path;
- model path;
- model SHA-256.

Meaning: transcript text was inferred locally by the configured model.

### No transcript capability

When captions are unavailable and no valid Whisper configuration exists, status is written but the build ultimately fails because a successful ReasonPack requires `transcript.txt`.

## Integrity semantics

SHA-256 answers:

> “Are these bytes the same bytes recorded by this pack?”

It does not answer:

- Is the video accurate?
- Is the speaker correct?
- Is the transcript semantically faithful?
- Is redistribution allowed?
- Is the source still available?
- Is a later rebuild from the same URL identical?

Those are separate questions.

## Rebuild semantics

ReasonPack is not currently a bit-for-bit remote-source reproducibility system. YouTube may change source encodes, captions, metadata, availability or adaptive stream selection. Tool versions may also change.

Therefore:

- preserve the verified pack when exact evidence matters;
- do not assume rerunning the URL later recreates the same bytes;
- compare manifests if a source is reacquired;
- treat a changed pack as a new evidence snapshot rather than silently replacing the old one.

## Safe modification rule

Never “fix” a failed verification by editing `SHA256SUMS.txt` or `manifest.json` to match unexplained changes unless your explicit intent is to create a **new** pack/version and you understand why the bytes changed.

Verification is supposed to detect drift. Teaching it to ignore drift defeats the product.
