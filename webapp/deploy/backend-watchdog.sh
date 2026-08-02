#!/usr/bin/env bash
# Runs the FastAPI backend (uvicorn, single worker — required, see README)
# and restarts it if it ever exits.
set -u
export PATH="/usr/bin:/mingw64/bin:/c/Windows/System32:$PATH"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"
VENV_PY="$BACKEND_DIR/.venv/Scripts/python.exe"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/backend.log"
mkdir -p "$LOG_DIR"

if [ ! -f "$VENV_PY" ]; then
  echo "[watchdog] $(date) - venv not found at $VENV_PY. Run the one-time setup in README.md first." >> "$LOG_FILE"
  exit 1
fi

cd "$BACKEND_DIR" || exit 1

while true; do
  "$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 >> "$LOG_FILE" 2>&1
  {
    echo ""
    echo "[watchdog] $(date) - backend exited, restarting in 3s"
  } >> "$LOG_FILE"
  sleep 3
done
