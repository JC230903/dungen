#!/usr/bin/env bash
# Runs a Cloudflare Quick Tunnel (no Cloudflare account/domain needed) and
# restarts it if it ever exits.
#
# NOTE: a quick tunnel's public *.trycloudflare.com URL is random and
# changes every time it restarts. Check logs/tunnel.log (or run
# check-url.sh) for the current one.
set -u
export PATH="/usr/bin:/mingw64/bin:/c/Windows/System32:$PATH"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/tunnel.log"
CF_EXE="$SCRIPT_DIR/bin/cloudflared.exe"
mkdir -p "$LOG_DIR"

if [ ! -f "$CF_EXE" ]; then
  echo "[watchdog] $(date) - cloudflared.exe not found at $CF_EXE. Run the one-time setup in README.md first." >> "$LOG_FILE"
  exit 1
fi

cd "$SCRIPT_DIR" || exit 1

while true; do
  "$CF_EXE" tunnel --url http://127.0.0.1:8080 --no-autoupdate >> "$LOG_FILE" 2>&1
  {
    echo ""
    echo "[watchdog] $(date) - tunnel exited, restarting in 3s (URL will change)"
  } >> "$LOG_FILE"
  sleep 3
done
