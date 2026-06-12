#!/usr/bin/env bash
set -euo pipefail

# Development contract for the future packaged desktop supervisor.
# It is intentionally conservative: it starts only the app-owned backend,
# waits for /health, writes logs, and never kills unrelated processes by port.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
APP_DATA_DIR="${AI_WORKSPACE_APP_DATA_DIR:-$BACKEND_DIR/.ai-workbench}"
LOG_DIR="$APP_DATA_DIR/logs"
SUPERVISOR_LOG="$LOG_DIR/desktop-supervisor.log"
BACKEND_LOG="$LOG_DIR/backend.log"
HEALTH_URL="http://$HOST:$PORT/health"
BACKEND_PID=""

mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "$SUPERVISOR_LOG"; }

port_busy() {
  python3 - "$HOST" "$PORT" <<'PY'
import socket
import sys
host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.2)
try:
    result = s.connect_ex((host, port))
    sys.exit(0 if result == 0 else 1)
finally:
    s.close()
PY
}

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Stopping app-owned backend PID $BACKEND_PID"
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

log "Preparing local desktop runtime"
log "Root: $ROOT_DIR"
log "Logs: $LOG_DIR"
log "Health: $HEALTH_URL"

if [[ ! -d "$BACKEND_DIR" ]]; then
  log "ERROR: backend directory not found: $BACKEND_DIR"
  exit 1
fi

if port_busy; then
  log "ERROR: $HOST:$PORT is already in use. Refusing to kill unknown process."
  log "Close the other process or configure a different app-owned port in a future packaged build."
  exit 2
fi

log "Starting private backend on $HOST:$PORT"
(
  cd "$BACKEND_DIR"
  APP_ENV="desktop" \
  HOST="$HOST" \
  PORT="$PORT" \
  AI_WORKSPACE_APP_DATA_DIR="$APP_DATA_DIR" \
  python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT"
) >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
log "Backend PID: $BACKEND_PID"

log "Waiting for backend health"
for attempt in $(seq 1 60); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    log "Backend is ready"
    log "Open UI with API base URL: http://$HOST:$PORT"
    log "Development contract complete. Press Ctrl+C to stop the app-owned backend."
    wait "$BACKEND_PID"
    exit $?
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "ERROR: backend exited before becoming healthy. Check $BACKEND_LOG"
    exit 3
  fi
  sleep 1
done

log "ERROR: backend did not become healthy in time. Check $BACKEND_LOG"
exit 4
