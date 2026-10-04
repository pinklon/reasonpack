# Installation and Removal Guide

## Before you install

ReasonPack writes a small user-local executable and shell aliases. The bootstrap may also install operating-system packages.

If you are on a managed corporate endpoint, use your organization’s approved software distribution/repository process when required. Do not bypass endpoint controls merely to make the demo work.

## What the reference installers change

### Common

The installers copy the reference executable to:

```text
~/.local/share/reasonpack/reasonpack
```

and expose:

```text
~/.local/bin/reasonpack
~/.local/bin/yt
~/.local/bin/rp
```

They add `~/.local/bin` to the appropriate shell profile when the package marker is not already present.

### macOS dependency behavior

`install/install-macos.sh` requires Homebrew. It installs these formulae only when missing:

- `yt-dlp`
- `ffmpeg`
- `python`

It does not automatically upgrade already-installed packages solely because a newer version exists.

### Linux dependency behavior

`install/install-linux.sh` detects:

- apt;
- dnf;
- pacman.

It installs ffmpeg/Python prerequisites through the OS package manager and creates:

```text
~/.local/share/reasonpack/venv
```

for a user-local `yt-dlp` installation.

The script does **not** add third-party RPM repositories when ffmpeg is unavailable. That is an enterprise/operator policy decision.

### Windows behavior

`install/install-windows-wsl.ps1` is a bootstrap into WSL.

If WSL is already installed, it maps the kit directory into Linux and runs the Linux installer.

If WSL is absent, the script exits with instructions. An administrator may explicitly rerun with `-InstallWSL` if enterprise policy permits.

A Windows restart may be required after first enabling WSL.

## macOS installation

From the unpacked kit:

```bash
chmod +x install/install-macos.sh
./install/install-macos.sh
```

Open a new Terminal afterward, then run:

```bash
reasonpack doctor
reasonpack self-test
```

Expected outcome: required commands are reported available and self-test prints a PASS message.

### macOS without Homebrew

This reference package does not install Homebrew automatically. Install dependencies through an approved method, place them on `PATH`, then manually install the ReasonPack script if necessary.

ReasonPack itself has no Homebrew-specific runtime requirement. Homebrew is simply the reference dependency bootstrap on macOS.

## Ubuntu/Debian installation

```bash
chmod +x install/install-linux.sh
./install/install-linux.sh
```

The script may request `sudo` for OS package installation. The ReasonPack executable and yt-dlp venv remain user-local.

Open a new shell, then:

```bash
reasonpack doctor
reasonpack self-test
```

## Fedora/RHEL-family installation

Use the same Linux script:

```bash
./install/install-linux.sh
```

If ffmpeg is unavailable in your approved repository configuration, the installer will stop. Configure the approved repository through your normal endpoint process, then rerun.

The kit intentionally does not install a random third-party repository on your behalf.

## Arch-family installation

```bash
./install/install-linux.sh
```

The pacman path installs ffmpeg/Python prerequisites and then creates the local yt-dlp venv.

## Windows 11 with WSL

From PowerShell in the unpacked directory:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install\install-windows-wsl.ps1
```

`Set-ExecutionPolicy -Scope Process` affects only the current PowerShell process.

If WSL is not installed and policy permits:

```powershell
.\install\install-windows-wsl.ps1 -InstallWSL
```

After WSL installation/restart, rerun the normal bootstrap.

Then enter WSL and verify:

```bash
reasonpack doctor
reasonpack self-test
```

## Optional Whisper configuration

ReasonPack does not silently install speech models.

After separately installing an approved `whisper-cli` and model:

```bash
export WHISPER_CLI="$HOME/path/to/whisper-cli"
export WHISPER_MODEL="$HOME/path/to/ggml-model.bin"
reasonpack doctor
```

Persist those environment variables only if that is appropriate for your workstation and model location.

`doctor` should report `whisper configured`.

## First real build

```bash
yt "https://www.youtube.com/watch?v=VIDEO_ID"
```

Or choose an exact output directory:

```bash
reasonpack build \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  "$HOME/Desktop/My ReasonPack"
```

## Verify installation without network

The kit includes a synthetic example:

```bash
reasonpack verify examples/sample-reasonpack
```

and package-level tests:

```bash
./tests/test-package.sh
```

The package test does not prove YouTube is reachable. It proves local script syntax and verification behavior.

## Manual removal

### Remove ReasonPack executable/aliases

```bash
rm -f ~/.local/bin/reasonpack ~/.local/bin/yt ~/.local/bin/rp
rm -rf ~/.local/share/reasonpack
```

On Linux/WSL this removes the ReasonPack-specific yt-dlp venv too.

### Remove shell profile block

Remove the block labeled:

```text
# >>> REASONPACK REF KIT >>>
...
# <<< REASONPACK REF KIT <<<
```

from `~/.zshrc` or `~/.bashrc`.

### Do not automatically uninstall shared dependencies

Homebrew/OS packages such as Python and ffmpeg may be used by other tools. This kit intentionally does not provide a script that blindly removes them.

## Upgrade posture

The reference kit does not yet ship an automatic updater. For a new release:

1. retain any ReasonPacks you care about;
2. inspect the new release/change log;
3. rerun the new installer;
4. run `doctor` and `self-test`;
5. verify an existing pack to confirm backward compatibility.

See `ROADMAP.md` for lifecycle improvements.
