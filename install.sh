#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
DEST="$PREFIX/bin/reasonpack"
mkdir -p "$(dirname "$DEST")"
install -m 755 "$HERE/bin/reasonpack" "$DEST"
printf 'Installed: %s\n' "$DEST"
case ":$PATH:" in
  *":$PREFIX/bin:"*) ;;
  *) printf 'NOTE: add %s/bin to PATH\n' "$PREFIX" ;;
esac
