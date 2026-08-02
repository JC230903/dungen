#!/usr/bin/env bash
# Runs Caddy (static frontend + /api reverse proxy) and restarts it if it
# ever exits.
set -u
export PATH="/usr/bin:/mingw64/bin:/c/Windows/System32:$PATH"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/caddy.log"
CADDY_EXE="$SCRIPT_DIR/bin/caddy.exe"
CONFIG="$SCRIPT_DIR/Caddyfile"
mkdir -p "$LOG_DIR"

if [ ! -f "$CADDY_EXE" ]; then
  echo "[watchdog] $(date) - caddy.exe not found at $CADDY_EXE. Run the one-time setup in README.md first." >> "$LOG_FILE"
  exit 1
fi

cd "$SCRIPT_DIR" || exit 1

while true; do
  "$CADDY_EXE" run --config "$CONFIG" >> "$LOG_FILE" 2>&1
  {
    echo ""
    echo "[watchdog] $(date) - caddy exited, restarting in 3s"
  } >> "$LOG_FILE"
  sleep 3
done
