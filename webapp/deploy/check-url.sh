#!/usr/bin/env bash
# Prints the current public URL from the tunnel log (most recent one wins
# — quick tunnel URLs change on every restart).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/tunnel.log"

if [ ! -f "$LOG_FILE" ]; then
  echo "No tunnel log yet — is the tunnel running?"
  exit 1
fi

URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | tail -1)

if [ -n "$URL" ]; then
  echo "$URL"
else
  echo "No URL found yet — tunnel may still be starting. Check logs/tunnel.log."
fi
