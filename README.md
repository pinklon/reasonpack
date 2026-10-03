# ReasonPack

ReasonPack turns one authorized YouTube source into a **verifiable local research pack** for humans and AI systems.

It combines `yt-dlp`, `ffmpeg`, `ffprobe`, source captions, optional local Whisper transcription, manifests, and SHA-256 verification into one small CLI. The result is not just a download. It is a closed evidence package whose media, transcript, metadata, and hashes can be inspected and reproduced.

## Output

```text
pack/
  video.mp4
  audio.m4a
  transcript.txt
  transcript-status.json
  source.json
  ffprobe.json
  captions.vtt              # when source captions exist
  manifest.json
  SHA256SUMS.txt
```

`verify` rejects missing files, empty required evidence, hash mismatches, and untracked regular files.

## Why

Downloading a video is easy. Preserving enough provenance to reason about it later without confusing a generated transcript for source truth is the useful part.

ReasonPack is built for research workflows where the same source may be reviewed by people, local tools, coding agents, or frontier models. Media remains primary evidence. Transcripts are searchable projections.

## Commands

```bash
reasonpack version
reasonpack doctor
reasonpack inspect 'https://www.youtube.com/watch?v=VIDEO_ID'
reasonpack build 'https://www.youtube.com/watch?v=VIDEO_ID' ./pack
reasonpack verify ./pack
reasonpack self-test
```

The CLI intentionally accepts canonical YouTube hosts only: `youtube.com`, `www.youtube.com`, `m.youtube.com`, and `youtu.be`.

## Dependencies

Required: `yt-dlp`, `ffmpeg`, `ffprobe`, `python3`, and `shasum`.

Optional local transcription fallback: `whisper-cli` from whisper.cpp plus a local GGML Whisper model. Explicit `WHISPER_CLI` and `WHISPER_MODEL` environment variables always win. If unset, ReasonPack looks for `whisper-cli` on `PATH` and then checks:

```text
~/.local/share/reasonpack/whisper/ggml-small.en.bin
~/.local/share/ghostmesh/whisper/ggml-small.en.bin
```

No cloud transcription provider is called by ReasonPack.

## Install

```bash
git clone https://github.com/pinklon/reasonpack.git
cd reasonpack
./install.sh
reasonpack doctor
```

The installer copies the CLI into `~/.local/bin` by default. It does not silently install dependencies.

Override the prefix with `PREFIX=/usr/local ./install.sh`.

On macOS, a typical dependency install is:

```bash
brew install yt-dlp ffmpeg whisper-cpp
```

A Whisper model is separate. Set `WHISPER_MODEL` to the local model you intend to use.

## Verification model

1. `yt-dlp` acquires source media and metadata.
2. `ffmpeg` normalizes video and audio.
3. Source captions are preferred when available.
4. Local Whisper may be used only as a local fallback.
5. Every retained evidence member is hashed into the manifest.
6. `SHA256SUMS.txt` independently closes the package.
7. `reasonpack verify` checks integrity and membership closure.

Speech recognition remains inference. Hashing and package closure do not.

## Scope

ReasonPack does not bypass DRM, authentication, access controls, paywalls, or platform restrictions. Use it only for material you own or are authorized or legally permitted to download and analyze. You are responsible for applicable law and platform terms.

ReasonPack does not upload, publish, redistribute, or call reasoning models on its own.

## Status

`v1.0.1` is the first standalone public release, extracted from a production research workflow and hardened around deterministic provenance and local verification.

See [ROADMAP.md](ROADMAP.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
