# Dependency Map

## Dependency philosophy

ReasonPack delegates specialized work to mature local tools rather than reimplementing media/network/speech stacks in one script.

The important design rule is that dependencies remain **explicit and inspectable**. The runtime does not silently install them. Installation is an operator-owned action performed by the bootstrap scripts or an enterprise-approved software process.

## Required runtime dependencies

| Dependency | Required | Product role | Why it exists |
|---|---:|---|---|
| Bash | Yes | CLI/orchestration runtime | current ReasonPack implementation is a Bash executable |
| Python 3 | Yes | URL validation, JSON/manifest/hash logic | uses standard library; avoids additional Python runtime packages in core |
| `yt-dlp` | Yes | source metadata/media/caption acquisition | isolates YouTube/site adaptation behind a mature acquisition tool |
| `ffmpeg` | Yes | video/audio normalization | produces stable local analysis formats |
| `ffprobe` | Yes | normalized media metadata | records technical stream/container facts |
| SHA-256 facility | Yes | integrity | `shasum`, `sha256sum`, or Python fallback |
| network access to source | Build only | YouTube acquisition | inspect/build cannot work offline against a remote URL |

## Optional dependency

| Dependency | Required | Role | Activation |
|---|---:|---|---|
| `whisper-cli` | No | speech-to-text fallback | only when captions are absent and operator explicitly configures it |
| Whisper model file | No | local speech model | `WHISPER_MODEL` must reference an existing local file |

Whisper is intentionally not installed by the standard ReasonPack runtime or default bootstrap because model choice, size, licensing, performance and enterprise software policy vary materially.

## No downstream-AI dependency

None of these are required to build or verify a ReasonPack:

- ChatGPT;
- Codex;
- Claude;
- Microsoft Copilot;
- GitHub Copilot;
- SharePlane;
- Google Drive;
- an LLM API key.

Those systems may consume or store the resulting artifact later.

## Operating-system mapping

### macOS

Reference bootstrap uses Homebrew for:

- `yt-dlp`;
- `ffmpeg` / `ffprobe`;
- Python 3.

Bash and `shasum` are normally present, but the runtime also has a Python SHA-256 fallback.

### Debian/Ubuntu family

Reference bootstrap uses apt for:

- `ffmpeg`;
- Python 3;
- Python venv support;
- CA certificates.

`yt-dlp` is installed inside a user-local ReasonPack Python venv so the product does not depend on the distribution shipping a sufficiently current package.

### Fedora/RHEL family

Reference bootstrap uses `dnf` for ffmpeg, Python/pip and CA certificates. `ffmpeg` availability depends on the organization’s enabled RPM repositories. The installer fails with guidance instead of configuring third-party repositories automatically.

### Arch family

Reference bootstrap uses `pacman` for ffmpeg, Python and pip, then creates the user-local venv for `yt-dlp`.

### Windows

The current supported architecture is **WSL**, not native PowerShell execution.

PowerShell is only a bootstrap entry point. The actual ReasonPack runtime and dependencies execute inside the selected WSL Linux distribution.

## User-local installation paths

The reference installers use:

```text
~/.local/share/reasonpack/reasonpack
~/.local/share/reasonpack/venv/        # Linux/WSL yt-dlp environment
~/.local/bin/reasonpack
~/.local/bin/yt
~/.local/bin/rp
```

macOS Homebrew provides `yt-dlp`; Linux/WSL link the venv’s `yt-dlp` into `~/.local/bin`.

## Dependency version posture

The current runtime records tool version lines in `manifest.json`, but this reference kit does **not** pin every third-party tool to one exact version.

Why:

- YouTube changes frequently and `yt-dlp` currency can matter;
- ffmpeg packaging differs across OS distributions;
- a false “universal pinned version” would not guarantee identical remote-source acquisition anyway.

Future release engineering should maintain a tested compatibility floor/range per supported OS rather than pretending version drift does not exist.

## Enterprise dependency concerns

Before broad rollout, validate:

- approved package repositories;
- outbound proxy behavior;
- TLS interception/custom CA requirements;
- executable allowlisting;
- local storage policy;
- ffmpeg codec/package availability;
- WSL policy on managed Windows devices;
- local Whisper/model licensing and storage if enabled.

See `SUPPORT_MATRIX.md` and `INSTALLATION.md`.
