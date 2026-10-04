# Product Feature Set

This document is the authoritative feature posture for the reference kit. It separates what the current runtime actually performs from roadmap ideas. Marketing illustrations, demos and future architecture notes do not override this file.

## Product in one sentence

ReasonPack converts one allowed YouTube URL into a local, provenance-preserving, hash-verifiable package of media, transcript and source evidence for later human or AI-assisted reasoning.

## CURRENT — implemented in the reference runtime

### 1. Source admission

**Capability:** Accept one explicit URL and reject unsupported hosts before acquisition.

Current allowed hosts:

- `youtube.com`
- `www.youtube.com`
- `m.youtube.com`
- `youtu.be`

The runtime does not expand arbitrary hosts and uses `--no-playlist` so one invocation means one source, not an accidental channel-sized acquisition.

**Why it matters:** source scope is part of the evidence boundary. A general-purpose downloader has a much larger authority and attack surface than this utility needs.

### 2. Source inspection

Command:

```bash
reasonpack inspect "URL"
```

Uses `yt-dlp --dump-single-json --skip-download --no-playlist` to expose source metadata before downloading media.

Typical use: confirm title, video ID, duration and available source metadata before committing time or bandwidth to a build.

### 3. Media acquisition

ReasonPack uses `yt-dlp` to obtain one best-available video/audio source suitable for local normalization.

The downloaded source file is **temporary working material**. After a successful build, ReasonPack removes the original downloaded carrier and retains the normalized evidence members instead.

### 4. Video normalization

Creates `video.mp4` with:

- H.264 video (`libx264`);
- `yuv420p` pixel format for broad playback compatibility;
- AAC audio when source audio exists;
- `+faststart` MP4 layout;
- CRF 23 / medium preset in the current reference runtime.

**Why normalize:** downstream reasoning tools and people should not have to understand every container/codec combination YouTube happens to serve.

### 5. Audio extraction

Creates `audio.m4a` with AAC audio at 128 kbps.

The audio member gives transcription and audio-only workflows a stable input without repeatedly extracting audio from video.

### 6. Technical media inspection

Creates `ffprobe.json` using `ffprobe` against the normalized MP4. This captures stream/container metadata independently from YouTube’s source metadata.

`source.json` describes the source. `ffprobe.json` describes the normalized output. They are different evidence roles.

### 7. Captions-first transcript strategy

ReasonPack attempts to retrieve English source subtitles or automatic captions in VTT format.

When captions exist:

- the selected VTT is retained as `captions.vtt`;
- caption markup/timing control lines are simplified into `transcript.txt`;
- `transcript-status.json` records `source-captions` provenance.

ReasonPack does not claim that source captions are human-verified or error-free.

### 8. Optional local Whisper fallback

When captions do not exist, ReasonPack may use local `whisper-cli` **only** when both are explicitly configured:

```bash
export WHISPER_CLI=/path/to/whisper-cli
export WHISPER_MODEL=/path/to/model.bin
```

The fallback:

1. converts audio to 16 kHz, mono, 16-bit PCM WAV;
2. invokes the configured local Whisper executable and model;
3. requires a non-empty transcript output;
4. records the Whisper executable path, model path and model SHA-256 in `transcript-status.json`.

If captions are absent and Whisper is not configured, the build fails rather than pretending the pack is complete.

### 9. Transcript status as evidence

`transcript-status.json` distinguishes at least:

- transcript derived from source captions;
- transcript derived from configured local Whisper;
- captions missing and no Whisper fallback configured.

This status is a provenance record, not a transcript-quality score.

### 10. Member manifest

`manifest.json` records:

- schema: `ghostmesh-reasoning-pack-v1`;
- source URL;
- tool version lines for `yt-dlp`, `ffmpeg`, `ffprobe` and `python3`;
- member path;
- member byte count;
- member SHA-256.

This allows a recipient to inspect exactly what bytes were sealed into that pack.

### 11. Independent checksum inventory

`SHA256SUMS.txt` records SHA-256 values for all tracked members plus `manifest.json`.

The checksum inventory is intentionally simple and readable by ordinary operating-system tools as well as the ReasonPack verifier.

### 12. Closed-pack verification

Command:

```bash
reasonpack verify "/path/to/pack"
```

Verification rejects:

- missing required members;
- empty required members;
- byte-count mismatch;
- SHA-256 mismatch;
- missing manifest/checksum records;
- unexplained regular files in the canonical pack directory.

**Important:** verification proves internal byte integrity against the recorded manifest. It does not prove source truth, copyright status, or transcript semantic accuracy.

### 13. Dependency diagnostics

```bash
reasonpack doctor
```

Reports availability/version information for the required local runtime and reports Whisper as optional, configured, unconfigured, or invalidly configured.

### 14. Built-in self-test

```bash
reasonpack self-test
```

The self-test exercises URL admission and verifies a synthetic pack. It also proves that an unexplained file causes verification to fail.

It is a runtime sanity check, not an end-to-end YouTube network test.

### 15. One-command convenience flow

```bash
yt "URL"
```

The reference distribution interprets a URL as a quick build request, fetches metadata for a human-readable folder name, and writes to:

```text
${REASONPACK_ROOT:-~/Desktop/Reasoning Packs}/<title> [video-id]/
```

An explicit output directory remains available through `reasonpack build URL OUT_DIR`.

### 16. Local-first / provider-neutral output

A ReasonPack is an ordinary directory of files. Building or verifying one does not require:

- SharePlane;
- Codex;
- Claude;
- Microsoft Copilot;
- GitHub;
- Google Drive;
- a cloud API key.

The acquisition step obviously requires network access to the permitted source. Transformation and verification are local.

### 17. No automatic upload, publication or telemetry

The current reference runtime:

- does not upload packs;
- does not publish packs;
- does not send usage telemetry;
- does not import browser cookies or private browsing state;
- does not automatically invoke an AI model.

## NEXT — useful extensions, not current behavior

These capabilities are candidates for a later derived-context layer or product increment:

- source-grounded summary generation;
- topic / concept extraction;
- chapter and timestamp citation index;
- selected keyframe extraction;
- batch source intake with explicit per-source identity;
- richer diagnostics and machine-readable doctor receipt;
- signed release manifests;
- updater / uninstaller lifecycle;
- enterprise proxy and certificate guidance;
- native Windows runtime rather than WSL;
- optional Execution Packet creation from a verified ReasonPack;
- normalized downstream execution receipts.

A design constraint for these features: **derived analysis should not silently mutate the canonical source-evidence pack**. It should be a separate artifact or explicitly versioned layer with provenance back to the pack it used.

## NOT YET — intentionally not implied by this kit

The current product is not:

- a knowledge graph;
- a team knowledge base;
- a remote storage service;
- a browser extension;
- a background monitoring service;
- a YouTube account/private-content importer;
- an enterprise search connector;
- an automatic AI-agent execution platform;
- an approval system;
- an identity/access-management system;
- a rights-management or copyright-clearance system.

Those may be adjacent systems. They are not current ReasonPack capabilities.
