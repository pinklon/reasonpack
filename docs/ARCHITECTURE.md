# Architecture

## Architectural objective

ReasonPack exists to make **source-derived context portable and inspectable without making the current AI session, model, or provider the system of record**.

The architecture therefore separates five concerns that are often mashed together in ad hoc AI workflows:

1. source admission;
2. source acquisition;
3. local normalization and transcript creation;
4. evidence packaging;
5. later reasoning or execution.

Only the first four belong to the current ReasonPack runtime.

## High-level flow

```text
YouTube URL
    │
    ▼
URL admission gate
    │
    ├── reject unsupported host
    ▼
yt-dlp inspection / acquisition
    │
    ├── source.json
    ├── temporary downloaded source media
    └── optional source captions
    │
    ▼
Local normalization
    │
    ├── ffmpeg → video.mp4
    ├── ffmpeg → audio.m4a
    └── ffprobe → ffprobe.json
    │
    ▼
Transcript strategy
    │
    ├── captions available → captions.vtt + transcript.txt
    └── no captions → optional configured local Whisper
    │
    ▼
Evidence seal
    │
    ├── transcript-status.json
    ├── manifest.json
    └── SHA256SUMS.txt
    │
    ▼
Closed-pack verification
    │
    ▼
Portable ReasonPack directory
```

See also `../diagrams/02-architecture-dependency-map.svg`.

## Component model

### A. CLI / orchestration layer

**Component:** `bin/reasonpack`

Responsibilities:

- command routing;
- URL validation;
- dependency detection;
- calling deterministic local tools;
- selecting transcript path;
- writing manifest/checksum evidence;
- verifying the final pack.

The CLI is orchestration, not a media codec, downloader, speech model, or AI reasoning engine.

### B. Acquisition adapter

**Component:** `yt-dlp`

Responsibilities:

- inspect YouTube source metadata;
- download one source media representation;
- request available subtitles / automatic captions.

Constraints:

- allowed host gate runs before acquisition;
- playlist expansion is disabled;
- private browser credentials/cookies are not imported by this reference runtime.

### C. Media normalization adapter

**Components:** `ffmpeg`, `ffprobe`

Responsibilities:

- create a broadly playable H.264/AAC MP4 analysis copy;
- create an AAC audio-only member;
- report technical stream/container metadata.

ReasonPack records output bytes and tool version lines rather than assuming a transcode is identical across every future ffmpeg build or platform.

### D. Transcript adapter

Two ordered strategies exist:

1. **Source captions** — preferred when available because they preserve a direct source-derived text path.
2. **Local Whisper fallback** — allowed only when explicitly configured by the operator.

The transcript path is evidence-bearing. `transcript-status.json` must explain which strategy produced the transcript.

### E. Integrity / package layer

**Components:** Python standard library plus platform SHA-256 command when available.

Responsibilities:

- calculate member sizes and hashes;
- produce `manifest.json`;
- produce `SHA256SUMS.txt`;
- verify required members;
- reject unexplained files.

This is the layer that converts “a folder of downloaded stuff” into a bounded artifact.

## Data contracts

### Input contract

Minimum input:

```text
one HTTP(S) URL whose hostname is in the explicit YouTube allowlist
```

Quick mode also accepts an optional output-root override.

The source URL is not itself proof that the user has redistribution rights.

### Canonical pack contract

Required evidence members are defined in `PACKAGE_CONTRACT.md`.

The pack directory is intentionally closed. Derived notes, AI summaries, presentations, prompts, or research should normally live **beside** the canonical pack or in a derived artifact that references its identity.

### Output identity

Current ReasonPack has no single semantic pack digest field. Instead it preserves:

- per-member byte size + SHA-256 in `manifest.json`;
- `manifest.json` SHA-256 in `SHA256SUMS.txt`;
- checksums for each recorded member.

A future signed/release identity can build on this without changing the meaning of the current manifest.

## Trust boundaries

### Boundary 1: network source

Everything obtained from YouTube is external input. Source metadata, media and captions may change over time.

ReasonPack does not assume a later rebuild from the same URL will produce byte-identical media. It records the bytes acquired in **this** pack.

### Boundary 2: local deterministic tooling

`ffmpeg`, `ffprobe`, Python and checksum tools transform/inspect local bytes. Their version lines are recorded in `manifest.json` where supported.

### Boundary 3: speech inference

Local Whisper is inference. It is optional and must never be described as deterministic truth. The model binary is hashed so the pack records which model was used.

### Boundary 4: downstream reasoning

Any later use by ChatGPT, Codex, Claude, Copilot or another system occurs **outside** ReasonPack’s current execution boundary.

A downstream AI may summarize a transcript incorrectly. That does not change the source-evidence pack unless someone explicitly creates a new artifact/version.

## Failure semantics

ReasonPack prefers an explicit incomplete/failure state over an apparently successful but misleading pack.

Examples:

- Unsupported URL host → reject before acquisition.
- Missing required dependency → fail with a visible dependency error.
- Source media unavailable → build does not continue as if normalization succeeded.
- Captions absent and Whisper unavailable → write transcript status, then fail because required transcript evidence is missing.
- Whisper exits strangely but no transcript file exists → do not trust process exit alone; fail transcript establishment.
- Member hash/size drift → verification fails.
- Extra file added to canonical directory → verification fails.

## Runtime boundaries and non-goals

The current architecture deliberately does not contain:

- account management;
- cookies/private source authentication;
- cloud storage;
- registry/database;
- AI summarization;
- vectorization;
- approval workflow;
- downstream model routing;
- publication.

Keeping these outside the core makes the context artifact usable in environments that do not share the same provider stack.

## Extension points

ReasonPack can evolve without turning into a monolith if extensions respect the boundaries:

- **New source adapter:** requires a new explicit admission/rights model, not silent expansion of the YouTube gate.
- **Derived-context adapter:** writes a separate derived artifact and references source-pack hashes.
- **Storage adapter:** copies exact pack bytes and verifies readback; storage location does not become pack identity.
- **Execution Packet adapter:** references verified pack members as exact work inputs and adds authority/acceptance semantics.
- **Signing adapter:** signs a defined manifest/release identity without replacing per-member integrity.

## Architectural invariant

**ReasonPack should remain useful even if every downstream AI provider changes tomorrow.**

That is the design test. If using the pack requires one specific model, conversation UI, vendor account, or cloud repository, we have coupled context to execution again.
