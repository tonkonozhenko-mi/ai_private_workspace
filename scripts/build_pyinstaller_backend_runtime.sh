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
FINGERPRINT_FILE="$OUTPUT_DIR/.build-fingerprint"
PROJECT_VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
PYTHON_BIN="${AI_PRIVATE_WORKSPACE_PACKAGING_PYTHON:-python3}"

# An explicitly provided packaging Python (e.g. an x86_64 venv for an Intel
# build) must win. Only fall back to the project venv when none was requested.
if [ -z "${AI_PRIVATE_WORKSPACE_PACKAGING_PYTHON:-}" ] \
  && [ -x "$PROJECT_VENV_PYTHON" ] \
  && "$PROJECT_VENV_PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
  PYTHON_BIN="$PROJECT_VENV_PYTHON"
fi

fail() { echo "❌ $1" >&2; exit 1; }
sha256_file() {
  "$PYTHON_BIN" - "$1" <<'PY'
import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}
json_escape() {
  "$PYTHON_BIN" - "$1" <<'PY'
import json, sys
print(json.dumps(sys.argv[1]))
PY
}

[ -f "$ENTRYPOINT" ] || fail "PyInstaller backend entrypoint missing: backend/packaging/pyinstaller_backend_entrypoint.py"
[ -f "$SPEC_FILE" ] || fail "PyInstaller spec missing: backend/packaging/ai_private_workspace_backend.spec"
[ -f "$BACKEND_DIR/requirements.txt" ] || fail "backend/requirements.txt missing"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python is required"

# Fingerprint every input that affects the frozen runtime (backend sources,
# requirements, the spec, and this build script). When nothing changed we can
# skip the slow PyInstaller rebuild entirely, so callers never need to invoke
# this step by hand — `build_and_open` runs it and it returns instantly when the
# backend is untouched. Set AI_PRIVATE_WORKSPACE_FORCE_BACKEND_BUILD=1 to force.
current_fingerprint() {
  "$PYTHON_BIN" - "$BACKEND_DIR" "$SPEC_FILE" "${BASH_SOURCE[0]}" <<'PY'
import hashlib, pathlib, sys
backend = pathlib.Path(sys.argv[1])
extra = [pathlib.Path(p) for p in sys.argv[2:]]
files = []
for base in (backend / "app", backend / "packaging"):
    if base.exists():
        files += sorted(base.rglob("*.py"))
req = backend / "requirements.txt"
if req.exists():
    files.append(req)
files += extra
digest = hashlib.sha256()
for path in sorted({str(f) for f in files}):
    p = pathlib.Path(path)
    try:
        data = p.read_bytes()
    except OSError:
        continue
    digest.update(path.encode())
    digest.update(b"\0")
    digest.update(data)
print(digest.hexdigest())
PY
}
FINGERPRINT="$(current_fingerprint)"

if [ "${AI_PRIVATE_WORKSPACE_FORCE_BACKEND_BUILD:-0}" != "1" ] \
  && [ -f "$MANIFEST" ] \
  && [ -f "$FINGERPRINT_FILE" ] \
  && [ "$(cat "$FINGERPRINT_FILE")" = "$FINGERPRINT" ] \
  && [ -x "$OUTPUT_DIR/ai-private-workspace-backend" ]; then
  printf '✅ Frozen backend already up to date (no backend changes) — skipping rebuild.\n'
  printf '   Force a rebuild with AI_PRIVATE_WORKSPACE_FORCE_BACKEND_BUILD=1\n'
  exit 0
fi

if ! "$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1; then
  fail "PyInstaller is not installed. Create backend/.venv and install packaging requirements, or set AI_PRIVATE_WORKSPACE_PACKAGING_PYTHON to a Python with PyInstaller."
fi

rm -rf "$OUTPUT_DIR" "$WORK_DIR" "$DIST_DIR"
mkdir -p "$OUTPUT_DIR"

# Ensure the bundled llama.cpp resource dir always exists so `tauri build` does
# not fail when llama-server has not been staged (e.g. a local Ollama-only
# build). CI's "Stage llama-server binary" step fills it for release builds.
mkdir -p "$ROOT_DIR/build/desktop/llama-runtime"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m PyInstaller \
  --clean \
  --noconfirm \
  --workpath "$WORK_DIR" \
  --distpath "$DIST_DIR" \
  "$SPEC_FILE"

# onedir layout: PyInstaller produces a folder (the COLLECT bundle) that holds
# the small launcher executable plus an _internal/ runtime directory. We stage
# the whole folder's contents into OUTPUT_DIR so the executable and _internal/
# stay siblings. This is what makes cold starts fast: nothing is unpacked to a
# temp dir on launch.
DIST_BUNDLE="$DIST_DIR/ai-private-workspace-backend"
[ -d "$DIST_BUNDLE" ] || fail "PyInstaller did not create the expected onedir bundle: $DIST_BUNDLE"

EXE_NAME="ai-private-workspace-backend"
if [ ! -x "$DIST_BUNDLE/$EXE_NAME" ]; then
  if [ -x "$DIST_BUNDLE/ai-private-workspace-backend.exe" ]; then
    EXE_NAME="ai-private-workspace-backend.exe"
  else
    fail "PyInstaller did not create the expected backend executable inside the bundle"
  fi
fi

# Copy the bundle contents (executable + _internal/ + datas) into OUTPUT_DIR.
cp -R "$DIST_BUNDLE/." "$OUTPUT_DIR/"
chmod +x "$OUTPUT_DIR/$EXE_NAME" 2>/dev/null || true

BINARY="$OUTPUT_DIR/$EXE_NAME"
BINARY_SHA="$(sha256_file "$BINARY")"
CREATED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
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

printf '%s\n' "$FINGERPRINT" > "$FINGERPRINT_FILE"

printf '✅ Frozen backend runtime created: %s\n' "$OUTPUT_DIR"
printf 'Executable: %s\n' "$OUTPUT_DIR/$(basename "$BINARY")"
printf 'Manifest: %s\n' "$MANIFEST"
printf 'Executable SHA256: %s\n' "$BINARY_SHA"
