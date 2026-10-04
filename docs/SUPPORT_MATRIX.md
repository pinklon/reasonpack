# Support Matrix

## Meaning of support labels

- **Reference-supported:** an install/bootstrap path is included and the runtime architecture is intentionally designed for it.
- **Conditional:** expected to work when OS repositories/policies provide dependencies, but environment-specific qualification is required.
- **Not current:** no first-class runtime/support claim is made.

This is a reference distribution, not an SLA-bearing production product.

## Runtime matrix

| Environment | Posture | Installation path | Notes |
|---|---|---|---|
| macOS on Apple Silicon | Reference-supported | `install-macos.sh` | Homebrew dependency model |
| macOS on Intel | Conditional | `install-macos.sh` | architecture is compatible; validate current Homebrew/package availability |
| Ubuntu/Debian Linux | Reference-supported | `install-linux.sh` | apt dependencies + user-local yt-dlp venv |
| Fedora/RHEL-like Linux | Conditional | `install-linux.sh` | ffmpeg may require organization-approved RPM repository |
| Arch-like Linux | Conditional | `install-linux.sh` | pacman path included |
| Windows 11 + WSL Ubuntu | Reference-supported architecture | `install-windows-wsl.ps1` → `install-wsl.sh` | ReasonPack runs inside Linux, not native Windows |
| Native Windows without WSL | Not current | none | roadmap item |
| Containers | Not packaged | manual | core should work in a Bash/Python/ffmpeg/yt-dlp image, but no supported image is shipped |

## Shell posture

The executable is Bash. POSIX `sh`, Fish, PowerShell and cmd.exe are not direct runtime targets.

Convenience profile integration currently targets:

- `~/.zshrc` on macOS;
- `~/.bashrc` on Linux by default;
- `~/.zshrc` on Linux if `$SHELL` indicates zsh.

## Network posture

| Operation | Network required? |
|---|---:|
| `reasonpack doctor` | No |
| `reasonpack self-test` | No |
| `reasonpack verify` | No |
| open local documentation | No |
| `reasonpack inspect URL` | Yes |
| `reasonpack build URL OUT_DIR` | Yes for source acquisition |
| `yt URL` | Yes for metadata + source acquisition |
| local Whisper fallback | No after model is installed |

## Downstream compatibility posture

A ReasonPack is ordinary files, so downstream systems can generally consume individual members according to their own file-upload rules. This kit does not claim every AI UI accepts the full directory or every media size.

The portable unit is the filesystem package and its evidence, not a guarantee about a particular vendor’s upload limit.

## Qualification required before enterprise rollout

Do not turn “reference-supported” into “enterprise-supported” without validating:

- corporate endpoint controls;
- proxy/TLS path;
- software distribution mechanism;
- supported ffmpeg codecs;
- local storage quotas;
- source/rights policy;
- WSL posture;
- update/removal lifecycle;
- help/support ownership.
