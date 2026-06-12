#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_DIR="$ROOT_DIR/frontend/src-tauri"

require_file() {
  local file_path="$1"
  if [[ ! -f "$file_path" ]]; then
    echo "Missing required Tauri scaffold file: $file_path" >&2
    exit 1
  fi
}

require_file "$TAURI_DIR/tauri.conf.json"
require_file "$TAURI_DIR/Cargo.toml"
require_file "$TAURI_DIR/build.rs"
require_file "$TAURI_DIR/src/main.rs"
require_file "$TAURI_DIR/src/lib.rs"
require_file "$ROOT_DIR/frontend/package.json"
require_file "$ROOT_DIR/backend/requirements.txt"

if ! grep -q "ai_private_workspace_lib::run();" "$TAURI_DIR/src/main.rs"; then
  echo "Tauri main.rs must delegate to ai_private_workspace_lib::run()." >&2
  exit 1
fi

if ! grep -q "get_supervisor_status" "$TAURI_DIR/src/lib.rs"; then
  echo "Missing Tauri supervisor status command scaffold in lib.rs." >&2
  exit 1
fi

if ! grep -q "get_supervisor_log_paths" "$TAURI_DIR/src/lib.rs"; then
  echo "Missing Tauri supervisor log path command scaffold in lib.rs." >&2
  exit 1
fi

if grep -R "pkill\|killall\|taskkill\|sh -c\|cmd /C\|powershell -Command" "$TAURI_DIR/src" >/dev/null 2>&1; then
  echo "Forbidden generic process/shell control found in Tauri scaffold." >&2
  exit 1
fi

cat <<MSG
Tauri shell scaffold looks ready.

Checked:
- frontend/src-tauri/tauri.conf.json
- frontend/src-tauri/Cargo.toml
- frontend/src-tauri/build.rs
- frontend/src-tauri/src/main.rs
- frontend/src-tauri/src/lib.rs
- frontend/package.json
- backend/requirements.txt

This script does not install Rust/Tauri, start backend, run scans, run MCP, or download models.
Current desktop startup is app-owned and frozen-manifest-gated; React still never gets arbitrary shell execution.
MSG
