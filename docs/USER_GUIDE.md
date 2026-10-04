# User Guide

## Mental model

ReasonPack is easiest to use if you think in three commands:

```text
inspect → build → verify
```

The `yt URL` shortcut simply combines metadata-based output naming with the normal build path.

## 1. Check your workstation

```bash
reasonpack doctor
```

This reports:

- ReasonPack version;
- yt-dlp availability/version;
- ffmpeg availability/version;
- ffprobe availability/version;
- Python availability/version;
- SHA-256 mechanism;
- optional Whisper configuration state.

Resolve required `MISSING` entries before a real build.

## 2. Run the self-test

```bash
reasonpack self-test
```

This is safe and offline. It proves basic runtime behavior and closed-pack verification.

Run it after installation and after meaningful dependency/runtime changes.

## 3. Inspect a source before download

```bash
reasonpack inspect "https://www.youtube.com/watch?v=VIDEO_ID" > source-preview.json
```

This does not download the video. It retrieves metadata through yt-dlp.

Useful preflight questions:

- Is this the intended source?
- Is the video ID correct?
- Is the duration reasonable for the task?
- Do I have authority/permission to acquire and analyze it?

## 4. Build with the quick command

```bash
yt "https://www.youtube.com/watch?v=VIDEO_ID"
```

Default root:

```text
${REASONPACK_ROOT:-~/Desktop/Reasoning Packs}
```

Folder naming uses source title plus video ID so two similarly named videos are less likely to collide semantically.

Example shape:

```text
~/Desktop/Reasoning Packs/
└── Example Architecture Talk [abc123]/
    ├── video.mp4
    ├── audio.m4a
    ├── transcript.txt
    ├── transcript-status.json
    ├── source.json
    ├── ffprobe.json
    ├── captions.vtt        # when source captions are used
    ├── manifest.json
    └── SHA256SUMS.txt
```

## 5. Build to an exact directory

Use explicit build mode when output location matters:

```bash
reasonpack build \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  "/absolute/or/relative/output/path"
```

The directory is created if needed.

Avoid building into a directory that already contains unrelated regular files. The final closed-pack verifier will reject unexplained files.

## 6. Read transcript provenance first

Before relying on `transcript.txt`, inspect:

```bash
cat transcript-status.json
```

### `source-captions`

The transcript was simplified from the retained VTT captions.

### `local-whisper-fallback`

The transcript came from local speech inference. The status record includes model identity information.

Automatic captions and speech recognition can both be wrong. Use the audio/video when exact wording matters.

## 7. Verify a pack later

```bash
reasonpack verify "/path/to/pack"
```

Expected success:

```text
PASS reasoning pack verification
```

Run verification:

- before handing the pack to someone else;
- after copying it between storage systems;
- before using it as exact downstream work input;
- when a teammate says “I think somebody added a file to this folder.”

## 8. Keep derived analysis outside the canonical pack

Do not drop `summary.md`, `notes.txt`, screenshots or model outputs into a verified ReasonPack directory unless you are intentionally creating a new artifact/version and updating its contract.

Recommended:

```text
Research Case/
├── source-reasonpack/
└── derived-analysis/
    ├── summary.md
    ├── architecture-notes.md
    └── prompts.md
```

This preserves the distinction between source evidence and interpretation.

## 9. Configure a custom default output root

```bash
export REASONPACK_ROOT="$HOME/Documents/Reasoning Packs"
```

Then `yt URL` writes beneath that root.

For a shared/cloud-synced folder, first consider source sensitivity, sync policy and storage size. ReasonPack itself does not require or assume cloud storage.

## 10. Optional local Whisper fallback

Configure only when you have an approved local executable/model:

```bash
export WHISPER_CLI=/path/to/whisper-cli
export WHISPER_MODEL=/path/to/model.bin
reasonpack doctor
```

When source captions are available they remain the preferred path in the current runtime.

## 11. What to hand another AI tool

It depends on the task and vendor upload limits.

Typical minimal reasoning input:

- `transcript.txt`;
- `source.json`;
- `transcript-status.json`;
- `manifest.json`.

For visual or audio analysis, include `video.mp4` or `audio.m4a` if the target surface accepts them.

Do not assume a downstream model read every file merely because you uploaded a directory or archive. That is the downstream system’s execution concern.

## 12. Example verification workflow after copying

```bash
# source workstation
reasonpack verify "$PACK"

# copy using your approved method
# ...

# destination workstation
reasonpack verify "$COPIED_PACK"
```

If the destination fails verification, investigate the bytes. Do not update hashes merely to silence the error.

## Command reference

```text
reasonpack doctor
    Check local required/optional dependencies.

reasonpack inspect URL
    Return source metadata without downloading media.

reasonpack build URL OUT_DIR
    Build one exact ReasonPack into OUT_DIR.

reasonpack verify OUT_DIR
    Validate pack schema, members, sizes, hashes and closure.

reasonpack self-test
    Offline local runtime/verification sanity test.

reasonpack URL [OUTPUT_ROOT]
yt URL [OUTPUT_ROOT]
rp URL [OUTPUT_ROOT]
    Convenience quick-build mode.
```

## Operational habit worth keeping

When a source becomes important to a decision, **preserve the verified pack you used**. A remote source can change or disappear. The URL is a locator; it is not a durable copy of the evidence you actually reasoned over.
