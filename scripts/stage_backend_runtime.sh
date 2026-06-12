#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
STAGE_DIR="${AI_PRIVATE_WORKSPACE_RUNTIME_STAGE_DIR:-$ROOT_DIR/build/desktop/backend-runtime}"
APP_STAGE_DIR="$STAGE_DIR/app"
MANIFEST="$STAGE_DIR/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"
LAUNCHER="$STAGE_DIR/run_backend.sh"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"

fail() {
  echo "❌ $1" >&2
  exit 1
}

sha256_file() {
  python3 - "$1" <<'PY'
import hashlib
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}

json_escape() {
  python3 - "$1" <<'PY'
import json
import sys
print(json.dumps(sys.argv[1]))
PY
}

[ -d "$BACKEND_DIR/app" ] || fail "backend/app not found. Run from the ai_workspace project root."
[ -f "$BACKEND_DIR/app/main.py" ] || fail "backend/app/main.py not found."
[ -f "$REQUIREMENTS" ] || fail "backend/requirements.txt not found."
command -v python3 >/dev/null 2>&1 || fail "python3 is required."

rm -rf "$STAGE_DIR"
mkdir -p "$APP_STAGE_DIR"

# Stage only source runtime inputs. Do not copy local DBs, venvs, caches, or build output.
cp -R "$BACKEND_DIR/app" "$APP_STAGE_DIR/"
find "$APP_STAGE_DIR" \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".venv" \) -prune -exec rm -rf {} +
find "$APP_STAGE_DIR" \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" -o -name "*.pyc" -o -name "*.pyo" \) -type f -delete
cp "$REQUIREMENTS" "$STAGE_DIR/requirements.txt"

PYTHON_VERSION="$(python3 - <<'PY'
import platform
print(platform.python_version())
PY
)"
REQUIREMENTS_SHA="$(sha256_file "$REQUIREMENTS")"
APP_SOURCE_COUNT="$(find "$BACKEND_DIR/app" -type f -name '*.py' | wc -l | tr -d ' ')"
MANIFEST_CREATED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$RUNTIME_DIR/app"
HOST="${AI_PRIVATE_WORKSPACE_HOST:-127.0.0.1}"
PORT="${AI_PRIVATE_WORKSPACE_PORT:-8000}"
APP_DATA_DIR="${AI_WORKSPACE_APP_DATA_DIR:-$HOME/Library/Application Support/AI Private Workspace}"
LOG_DIR="$APP_DATA_DIR/logs"

mkdir -p "$LOG_DIR"

export APP_ENV="${APP_ENV:-desktop}"
export HOST="$HOST"
export PORT="$PORT"
export AI_WORKSPACE_APP_DATA_DIR="$APP_DATA_DIR"
export AI_WORKBENCH_DB_PATH="${AI_WORKBENCH_DB_PATH:-$APP_DATA_DIR/workspace.db}"

cd "$APP_DIR"
exec python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT"
EOF
chmod +x "$LAUNCHER"

cat > "$MANIFEST" <<EOF
{
  "name": "AI Private Workspace backend runtime",
  "status": "staged_source_runtime",
  "created_at": $(json_escape "$MANIFEST_CREATED_AT"),
  "runtime_stage_dir": $(json_escape "$STAGE_DIR"),
  "backend_source": "backend/app",
  "staged_app_dir": "app/app",
  "launcher": "run_backend.sh",
  "requirements": "requirements.txt",
  "requirements_sha256": $(json_escape "$REQUIREMENTS_SHA"),
  "python_available_during_staging": $(json_escape "$PYTHON_VERSION"),
  "backend_python_files": $APP_SOURCE_COUNT,
  "strategy": "source runtime staging first; frozen binary with PyInstaller/Nuitka is the next packaging milestone",
  "safety_rules": [
    "staging does not start backend",
    "staging does not scan, index, rebuild, start MCP, start Agent, or download models",
    "runtime data and logs stay outside the staged runtime directory",
    "frontend still cannot execute shell commands"
  ]
}
EOF

printf '✅ Backend runtime staged: %s\n' "$STAGE_DIR"
printf 'Manifest: %s\n' "$MANIFEST"
printf 'Launcher: %s\n' "$LAUNCHER"
printf 'Requirements SHA256: %s\n' "$REQUIREMENTS_SHA"
