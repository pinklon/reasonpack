#!/usr/bin/env bash
set -euo pipefail
umask 027

STATE=/srv/ghostmesh/workspaces/state/reasonpack
ARTIFACTS=/srv/ghostmesh/workspaces/artifacts/reasonpack
BIN=/home/ghostmesh/.local/bin
WORKER="$BIN/ghostmesh-reasonpack-intake"
PROVIDER=/home/ghostmesh/.local/share/reasonpack/bgutil-ytdlp-pot-provider/server/build/main.js
COLLAB_ENV=/srv/ghostmesh/workspaces/state/ghostmesh-collab/collab.env

mkdir -p "$STATE" "$STATE/receipts" "$ARTIFACTS" /home/ghostmesh/.local/log
chmod 750 "$STATE" "$STATE/receipts" "$ARTIFACTS"

if [[ -f "$COLLAB_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$COLLAB_ENV"
  set +a
fi

if [[ -f "$PROVIDER" ]]; then
  ppid=""
  [[ -f "$STATE/bgutil.pid" ]] && ppid="$(cat "$STATE/bgutil.pid" 2>/dev/null || true)"
  if [[ -z "$ppid" || ! "$ppid" =~ ^[0-9]+$ || ! -d "/proc/$ppid" ]]; then
    nohup /usr/bin/node "$PROVIDER" --host 127.0.0.1 --port 4416 \
      >>"$STATE/bgutil.log" 2>&1 </dev/null &
    echo "$!" >"$STATE/bgutil.pid"
  fi
fi

wpid=""
[[ -f "$STATE/intake.pid" ]] && wpid="$(cat "$STATE/intake.pid" 2>/dev/null || true)"
if [[ -n "$wpid" && "$wpid" =~ ^[0-9]+$ && -d "/proc/$wpid" ]]; then
  exit 0
fi

export PATH="$BIN:$PATH"
export REASONPACK_ROOT="$ARTIFACTS"
nohup /usr/bin/python3 "$WORKER" --daemon >>/home/ghostmesh/.local/log/ghostmesh-reasonpack-intake.log 2>&1 </dev/null &
echo "$!" >"$STATE/intake.pid"
