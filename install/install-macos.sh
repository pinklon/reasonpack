#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
command -v brew >/dev/null 2>&1 || { echo "Homebrew is required: https://brew.sh" >&2; exit 20; }
for pkg in yt-dlp ffmpeg python; do brew list --versions "$pkg" >/dev/null 2>&1 || brew install "$pkg"; done
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/reasonpack"
cp "$HERE/bin/reasonpack" "$HOME/.local/share/reasonpack/reasonpack"; chmod 755 "$HOME/.local/share/reasonpack/reasonpack"
for n in reasonpack yt rp; do ln -sf "$HOME/.local/share/reasonpack/reasonpack" "$HOME/.local/bin/$n"; done
PROFILE="$HOME/.zshrc"; touch "$PROFILE"
grep -q "REASONPACK REF KIT" "$PROFILE" || printf '
# >>> REASONPACK REF KIT >>>
export PATH="$HOME/.local/bin:$PATH"
# <<< REASONPACK REF KIT <<<
' >> "$PROFILE"
export PATH="$HOME/.local/bin:$PATH"
reasonpack self-test
reasonpack doctor
echo "PASS: installed. Open a new Terminal, then run: yt https://www.youtube.com/watch?v=VIDEO_ID"
