#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
if command -v apt-get >/dev/null 2>&1; then sudo apt-get update; sudo apt-get install -y ffmpeg python3 python3-venv ca-certificates; elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y ffmpeg python3 python3-pip ca-certificates || { echo "ffmpeg may require your approved RPM repository." >&2; exit 21; }; elif command -v pacman >/dev/null 2>&1; then sudo pacman -S --needed ffmpeg python python-pip; else echo "Unsupported automatic package manager. See docs/INSTALLATION.md." >&2; exit 22; fi
VENV="$HOME/.local/share/reasonpack/venv"; python3 -m venv "$VENV"; "$VENV/bin/python" -m pip install --upgrade pip yt-dlp
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/reasonpack"
cp "$HERE/bin/reasonpack" "$HOME/.local/share/reasonpack/reasonpack"; chmod 755 "$HOME/.local/share/reasonpack/reasonpack"
for n in reasonpack yt rp; do ln -sf "$HOME/.local/share/reasonpack/reasonpack" "$HOME/.local/bin/$n"; done
ln -sf "$VENV/bin/yt-dlp" "$HOME/.local/bin/yt-dlp"
PROFILE="$HOME/.bashrc"; [[ "${SHELL:-}" == */zsh ]] && PROFILE="$HOME/.zshrc"; touch "$PROFILE"
grep -q "REASONPACK REF KIT" "$PROFILE" || printf '
# >>> REASONPACK REF KIT >>>
export PATH="$HOME/.local/bin:$PATH"
# <<< REASONPACK REF KIT <<<
' >> "$PROFILE"
export PATH="$HOME/.local/bin:$PATH"
reasonpack self-test
reasonpack doctor
echo "PASS: installed. Open a new shell, then run: yt https://www.youtube.com/watch?v=VIDEO_ID"
