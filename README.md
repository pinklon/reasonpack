# ReasonPack Professional Reference Kit

**Capture once. Carry forward. Verify what you have.**

ReasonPack is a small local CLI for converting one authorized YouTube source into a portable evidence package containing normalized media, audio, transcript material, source metadata, technical metadata, a member manifest, and SHA-256 integrity records.

The utility is deliberately boring in the places where boring is valuable. Source acquisition is explicit. Transcript provenance is explicit. Missing dependencies fail visibly. Missing captions do not become an imaginary transcript. Files are hashed. Verification rejects drift and unexplained files. Nothing is silently uploaded to a cloud service or handed to an AI provider.

## Quick start

```bash
# macOS
./install/install-macos.sh

# Linux
./install/install-linux.sh

# Windows PowerShell, using WSL as the supported runtime
.\install\install-windows-wsl.ps1
```

Then:

```bash
reasonpack doctor
reasonpack self-test
yt "https://www.youtube.com/watch?v=VIDEO_ID"
```

`yt` and `rp` are convenience aliases for the same ReasonPack executable.

## What a successful pack contains

Required members:

- `video.mp4` — normalized H.264/AAC analysis copy.
- `audio.m4a` — extracted AAC audio.
- `transcript.txt` — transcript text from source captions or configured local Whisper fallback.
- `transcript-status.json` — provenance/status for transcript creation.
- `source.json` — source metadata captured by `yt-dlp`.
- `ffprobe.json` — normalized media stream/container metadata.
- `manifest.json` — tracked member names, sizes and SHA-256 identities plus tool versions.
- `SHA256SUMS.txt` — independent checksum inventory.

Optional member:

- `captions.vtt` — preserved source caption file when source captions were used.

The pack is **closed under its manifest**. `reasonpack verify` rejects missing files, empty required files, digest or byte-count drift, and unexplained regular files added to the canonical pack directory.

## What it does not do today

The current runtime does not automatically summarize, extract topics, generate keyframes, create embeddings, upload to Drive, sync to a team repository, or invoke Codex/Claude/Copilot. Those capabilities may be valuable, but they are deliberately separated from the current evidence-building core.

See `docs/PRODUCT_FEATURE_SET.md` for the authoritative CURRENT / NEXT / NOT YET contract.

## Why the package is larger than the script

The tool itself is small. The engineering context around it should not be mysterious.

This kit includes:

- product feature contract;
- architecture and package contracts;
- PRD and strategic vision;
- quality bar and success measures;
- operating model and dependency map;
- macOS, Linux and Windows/WSL onboarding paths;
- user and developer guides;
- troubleshooting and security/rights guidance;
- design decisions and tradeoffs;
- roadmap;
- optional bridge to Execution Packets;
- diagrams, synthetic example, checksums and manifest.

The intended lesson is not “write more documents.” It is **preserve the decisions that another capable person would otherwise have to rediscover**.
