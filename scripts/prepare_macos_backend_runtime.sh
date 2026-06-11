#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
BUILD_DIR="$ROOT_DIR/build/macos/backend-runtime"
MANIFEST="$BUILD_DIR/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"

fail() {
  echo "❌ $1" >&2
  exit 1
}

[ -d "$BACKEND_DIR/app" ] || fail "backend/app not found. Run from the ai_workspace project root."
[ -f "$REQUIREMENTS" ] || fail "backend/requirements.txt not found."
command -v python3 >/dev/null 2>&1 || fail "python3 is required for runtime manifest generation."

mkdir -p "$BUILD_DIR"

PYTHON_VERSION="$(python3 - <<'PY'
import platform
print(platform.python_version())
PY
)"

REQUIREMENTS_SHA="$(python3 - "$REQUIREMENTS" <<'PY'
import hashlib
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
)"

APP_SOURCE_COUNT="$(find "$BACKEND_DIR/app" -type f -name '*.py' | wc -l | tr -d ' ')"
TEST_SOURCE_COUNT="$(find "$BACKEND_DIR/tests" -type f -name '*.py' 2>/dev/null | wc -l | tr -d ' ' || true)"

cat > "$MANIFEST" <<EOF
AI Private Workspace backend runtime manifest

Status: foundation
Generated at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
Project root: $ROOT_DIR
Backend source: backend/app
Requirements: backend/requirements.txt
Requirements SHA256: $REQUIREMENTS_SHA
Python available during packaging: $PYTHON_VERSION
Backend Python files: $APP_SOURCE_COUNT
Backend test files: ${TEST_SOURCE_COUNT:-0}

Runtime strategy:
- Current foundation stages backend source in the macOS .app bundle.
- Final package should not require the user to create a venv manually.
- Next packaging stage should choose PyInstaller, Nuitka, or packaged Python runtime.

Required excludes for generated packages:
- backend/.ai-workbench/
- *.db
- *.sqlite
- *.sqlite3
- .venv/
- __pycache__/
- .pytest_cache/
- frontend/node_modules/
- frontend/dist/
- build/

Safety rules:
- Runtime preparation does not start scan/index/rebuild/MCP/agent/model downloads.
- Runtime data stays outside the app bundle.
- App updates must not overwrite user databases or logs.
EOF

printf '✅ Backend runtime manifest created: %s\n' "$MANIFEST"
printf 'Requirements SHA256: %s\n' "$REQUIREMENTS_SHA"
