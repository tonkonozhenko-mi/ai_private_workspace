#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
SPEC_FILE="$BACKEND_DIR/packaging/ai_private_workspace_backend.spec"
ENTRYPOINT="$BACKEND_DIR/packaging/pyinstaller_backend_entrypoint.py"
OUTPUT_DIR="${AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_DIR:-$ROOT_DIR/build/desktop/frozen-backend-runtime}"
WORK_DIR="$ROOT_DIR/build/desktop/pyinstaller-work"
DIST_DIR="$ROOT_DIR/build/desktop/pyinstaller-dist"
MANIFEST="$OUTPUT_DIR/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"

fail() { echo "❌ $1" >&2; exit 1; }
sha256_file() {
  python3 - "$1" <<'PY'
import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}
json_escape() {
  python3 - "$1" <<'PY'
import json, sys
print(json.dumps(sys.argv[1]))
PY
}

[ -f "$ENTRYPOINT" ] || fail "PyInstaller backend entrypoint missing: backend/packaging/pyinstaller_backend_entrypoint.py"
[ -f "$SPEC_FILE" ] || fail "PyInstaller spec missing: backend/packaging/ai_private_workspace_backend.spec"
[ -f "$BACKEND_DIR/requirements.txt" ] || fail "backend/requirements.txt missing"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
  fail "PyInstaller is not installed in this Python environment. Install it in a local packaging venv, then rerun: python3 -m pip install pyinstaller"
fi

rm -rf "$OUTPUT_DIR" "$WORK_DIR" "$DIST_DIR"
mkdir -p "$OUTPUT_DIR"

cd "$ROOT_DIR"
python3 -m PyInstaller \
  --clean \
  --noconfirm \
  --workpath "$WORK_DIR" \
  --distpath "$DIST_DIR" \
  "$SPEC_FILE"

BINARY="$DIST_DIR/ai-private-workspace-backend"
if [ ! -x "$BINARY" ]; then
  if [ -x "$DIST_DIR/ai-private-workspace-backend.exe" ]; then
    BINARY="$DIST_DIR/ai-private-workspace-backend.exe"
  else
    fail "PyInstaller did not create the expected backend executable"
  fi
fi

cp "$BINARY" "$OUTPUT_DIR/$(basename "$BINARY")"
chmod +x "$OUTPUT_DIR/$(basename "$BINARY")" 2>/dev/null || true

BINARY_SHA="$(sha256_file "$OUTPUT_DIR/$(basename "$BINARY")")"
CREATED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
PYTHON_VERSION="$(python3 - <<'PY'
import platform
print(platform.python_version())
PY
)"

cat > "$MANIFEST" <<EOF
{
  "name": "AI Private Workspace frozen backend runtime",
  "status": "pyinstaller_poc_built",
  "created_at": $(json_escape "$CREATED_AT"),
  "runtime_dir": $(json_escape "$OUTPUT_DIR"),
  "builder": "PyInstaller",
  "backend_executable": $(json_escape "$(basename "$BINARY")"),
  "backend_executable_sha256": $(json_escape "$BINARY_SHA"),
  "python_version": $(json_escape "$PYTHON_VERSION"),
  "entrypoint": "backend/packaging/pyinstaller_backend_entrypoint.py",
  "spec_file": "backend/packaging/ai_private_workspace_backend.spec",
  "safety_rules": [
    "build does not start backend",
    "build does not scan, index, rebuild, start MCP, start Agent, or download models",
    "frontend still cannot execute shell commands",
    "frozen runtime output stays under build/desktop and must not be committed"
  ]
}
EOF

printf '✅ Frozen backend runtime created: %s\n' "$OUTPUT_DIR"
printf 'Executable: %s\n' "$OUTPUT_DIR/$(basename "$BINARY")"
printf 'Manifest: %s\n' "$MANIFEST"
printf 'Executable SHA256: %s\n' "$BINARY_SHA"
