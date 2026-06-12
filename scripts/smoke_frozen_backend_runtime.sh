#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_DIR:-$ROOT_DIR/build/desktop/frozen-backend-runtime}"
MANIFEST="$OUTPUT_DIR/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"
HOST="${AI_PRIVATE_WORKSPACE_HOST:-127.0.0.1}"
PORT="${AI_PRIVATE_WORKSPACE_PORT:-8000}"
HEALTH_URL="http://$HOST:$PORT/health"
LOG_DIR="${AI_PRIVATE_WORKSPACE_SMOKE_LOG_DIR:-$ROOT_DIR/build/desktop/smoke-logs}"
LOG_FILE="$LOG_DIR/frozen-backend-smoke.log"
PID_FILE="$LOG_DIR/frozen-backend-smoke.pid"
APP_DATA_DIR="$LOG_DIR/app-data"
TIMEOUT_SECONDS="${AI_PRIVATE_WORKSPACE_SMOKE_TIMEOUT_SECONDS:-45}"

fail() { echo "❌ $1" >&2; exit 1; }
ok() { echo "✅ $1"; }
print_log_tail() {
  if [ -f "$LOG_FILE" ]; then
    echo "--- frozen backend log tail: $LOG_FILE ---" >&2
    tail -80 "$LOG_FILE" >&2 || true
    echo "--- end frozen backend log tail ---" >&2
  else
    echo "--- frozen backend log missing: $LOG_FILE ---" >&2
  fi
}

[ -f "$MANIFEST" ] || fail "Frozen runtime manifest missing. Run scripts/build_pyinstaller_backend_runtime.sh first."
command -v python3 >/dev/null 2>&1 || fail "python3 is required for safe manifest parsing and health checks"

BINARY_NAME="$(python3 - "$MANIFEST" <<'PY'
import json, pathlib, sys
manifest = pathlib.Path(sys.argv[1])
data = json.loads(manifest.read_text(encoding="utf-8"))
name = data.get("backend_executable")
if not isinstance(name, str) or not name.strip():
    raise SystemExit("manifest does not contain backend_executable")
if "/" in name or "\\" in name:
    raise SystemExit("backend_executable must be a filename, not a path")
print(name)
PY
)"
BINARY="$OUTPUT_DIR/$BINARY_NAME"
[ -x "$BINARY" ] || fail "Frozen backend executable missing or not executable: $BINARY"

python3 - "$HOST" "$PORT" <<'PY'
import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    result = sock.connect_ex((host, port))
if result == 0:
    raise SystemExit(f"port {host}:{port} is already in use; refusing to kill or replace unknown process")
PY

mkdir -p "$LOG_DIR" "$APP_DATA_DIR"
rm -f "$PID_FILE" "$LOG_FILE"

APP_ENV="desktop" \
APP_DATA_DIR="$APP_DATA_DIR" \
WORKSPACE_DB_PATH="$APP_DATA_DIR/workspaces.db" \
"$BINARY" --runtime-self-check >"$LOG_FILE" 2>&1 || {
  print_log_tail
  fail "frozen backend import preflight failed before startup"
}

cleanup() {
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

APP_ENV="desktop" \
APP_DATA_DIR="$APP_DATA_DIR" \
WORKSPACE_DB_PATH="$APP_DATA_DIR/workspaces.db" \
AI_PRIVATE_WORKSPACE_HOST="$HOST" \
AI_PRIVATE_WORKSPACE_PORT="$PORT" \
"$BINARY" >>"$LOG_FILE" 2>&1 &
PID="$!"
echo "$PID" > "$PID_FILE"
ok "started frozen backend PID $PID"

python3 - "$HEALTH_URL" "$TIMEOUT_SECONDS" "$PID" <<'PY'
import json, os, signal, sys, time, urllib.request
url = sys.argv[1]
deadline = time.time() + int(sys.argv[2])
pid = int(sys.argv[3])
last_error = None
while time.time() < deadline:
    try:
        os.kill(pid, 0)
    except OSError as exc:
        raise SystemExit(f"frozen backend process exited before health became ready: {exc}") from exc
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            body = response.read().decode("utf-8")
            if response.status == 200:
                try:
                    payload = json.loads(body)
                    status = payload.get("status", "unknown")
                except Exception:
                    status = "ok"
                print(f"health ok: {status}")
                raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001 - shell smoke prints last error
        last_error = exc
    time.sleep(0.5)
raise SystemExit(f"health check failed for {url}: {last_error}")
PY
status=$?
if [ "$status" -ne 0 ]; then
  print_log_tail
  exit "$status"
fi

ok "frozen backend smoke passed: $HEALTH_URL"
ok "log: $LOG_FILE"
ok "app data: $APP_DATA_DIR"
