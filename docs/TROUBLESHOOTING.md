# Troubleshooting Guide

Start with:

```bash
reasonpack doctor
reasonpack self-test
```

Those two commands separate local runtime problems from source/network problems quickly.

## Quick diagnostic table

| Symptom | Likely cause | Action |
|---|---|---|
| `missing dependency: yt-dlp` | install/profile path incomplete | rerun installer, open new shell, inspect `PATH` |
| `missing dependency: ffmpeg` | OS dependency unavailable | install from approved repository |
| URL rejected | host outside allowlist | use canonical YouTube URL or treat new source support as a product change |
| build stops with transcript unavailable | no captions and no valid Whisper fallback | configure local Whisper or use another authorized transcript source in a future explicit workflow |
| verify reports hash/size failure | pack bytes changed | compare against source copy; rebuild/reacquire only if intended |
| verify reports untracked files | derived/scratch file added to canonical directory | move it outside pack or create a new derived artifact |
| WSL bootstrap fails | WSL disabled/policy issue | enable through approved Windows process |
| dnf cannot install ffmpeg | repository not enabled | use organization-approved RPM repository |
| source download fails | YouTube/network/yt-dlp issue | inspect network, source availability, yt-dlp currency |

## Dependency problems

### `reasonpack: command not found`

Check:

```bash
ls -l ~/.local/bin/reasonpack
printf '%s\n' "$PATH" | tr ':' '\n'
```

If `~/.local/bin` is missing from PATH, open a new shell or source the relevant profile:

```bash
source ~/.zshrc   # zsh
source ~/.bashrc  # bash
```

### `yt-dlp` missing after Linux installation

The Linux installer places yt-dlp in a ReasonPack-specific venv and symlinks it into `~/.local/bin`.

Check:

```bash
ls -l ~/.local/share/reasonpack/venv/bin/yt-dlp
ls -l ~/.local/bin/yt-dlp
```

If the venv is damaged, remove only the ReasonPack venv and rerun the Linux installer.

### `ffmpeg` missing on Fedora/RHEL family

ReasonPack will not enable an unapproved third-party RPM repository automatically.

Use the repository configuration approved for your environment, then rerun:

```bash
reasonpack doctor
```

## Source admission problems

### `rejected source URL host`

ReasonPack currently accepts canonical YouTube hosts only.

This is intentional. Do not work around it by editing the URL-validation function for one source and then call the package “supported.” Adding another provider is a product/rights/security decision and should come with an adapter contract and tests.

### Playlist URL only acquires one video

This is expected. `--no-playlist` is part of the source-scope contract.

Batch/playlist intake is a future feature, not a bug workaround.

## Acquisition problems

### yt-dlp reports unavailable formats or site changes

First check:

```bash
yt-dlp --version
reasonpack inspect "URL"
```

YouTube changes often. A current yt-dlp build may be required.

On managed endpoints, update through the approved package/software process rather than downloading arbitrary executables into PATH.

### Enterprise proxy blocks access

ReasonPack does not currently contain an enterprise proxy abstraction.

Use your approved system/package/network configuration. Do not solve proxy restrictions by importing browser cookies or credentials into the tool unless a future explicit security design authorizes that behavior.

## Transcript problems

### `transcript unavailable; see transcript-status.json`

Inspect:

```bash
cat transcript-status.json
```

If the status is `missing-captions-and-no-whisper-fallback`, the source had no selected captions and local Whisper was not configured.

Configure Whisper only if desired/approved, then rebuild into a clean output directory.

### `whisper INVALID CONFIGURATION`

Run:

```bash
printf 'WHISPER_CLI=%s\n' "$WHISPER_CLI"
printf 'WHISPER_MODEL=%s\n' "$WHISPER_MODEL"
test -x "$WHISPER_CLI" && echo cli-ok
test -f "$WHISPER_MODEL" && echo model-ok
```

The CLI must be executable and the model path must be a regular file.

### Transcript exists but wording seems wrong

That is a content-quality issue, not a pack-integrity issue.

Check `transcript-status.json`, then compare the questionable passage against `captions.vtt`, audio or video.

Do not “correct” `transcript.txt` inside the canonical pack without intentionally creating a new artifact/version. A corrected transcript is derived work and should preserve its relationship to the original evidence.

## Verification problems

### Extra file rejected

Example:

```text
untracked pack members: ['summary.md']
```

This is expected. Move derived work outside the canonical pack.

### SHA-256 mismatch

Do not edit the checksum file first.

Investigate:

1. Which member changed?
2. Was the pack copied through a system that transformed content?
3. Did someone intentionally edit the file?
4. Is the original verified pack still available?

If the new bytes are intended, create a new pack/version and record the change.

### Byte count mismatch

Treat it like hash drift. A truncated or replaced file must not be accepted just because its filename is unchanged.

## Windows / WSL problems

### `wsl.exe` not found

WSL is not enabled or available. If policy permits, use the documented `-InstallWSL` option from elevated PowerShell. Otherwise use your enterprise software-management path.

### Kit is on a Windows path with spaces

The PowerShell bootstrap uses `wslpath` to translate the package path. If your environment has custom WSL mounts/policies, copy the kit to a simple local development directory and retry.

### `reasonpack` works inside WSL but not PowerShell

Expected. The current runtime is inside WSL. Native PowerShell/cmd execution is not a current feature.

## Useful exit/status classes in the reference script

The script uses distinct non-zero boundaries for common classes, including:

- usage error: 64;
- unsupported URL: validation failure before build;
- missing required dependency: 20;
- source media not established: build boundary around 30;
- transcript not established: build boundary around 31;
- malformed/missing pack contract: verification boundary around 40;
- self-test regressions: 90/91 class.

Callers should treat any non-zero result as failure and should not assume every future version preserves every numeric code unless the contract is formalized further.

## When to escalate instead of debugging locally forever

Escalate when:

- a previously qualified source class fails across multiple known-good systems;
- yt-dlp/site behavior changed materially;
- verification fails on an untouched known-good fixture;
- dependency installation requires a new repository/security exception;
- a requested feature would expand source authority or credential access;
- the only proposed fix is to weaken verification.

A good escalation includes `reasonpack doctor` output, command used, failure text, OS, and whether the included self-test passes. Do not include credentials/cookies.
