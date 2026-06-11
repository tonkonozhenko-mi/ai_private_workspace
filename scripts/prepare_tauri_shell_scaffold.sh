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
require_file "$ROOT_DIR/frontend/package.json"
require_file "$ROOT_DIR/backend/requirements.txt"

if ! grep -q "get_supervisor_status" "$TAURI_DIR/src/main.rs"; then
  echo "Missing Tauri supervisor status command scaffold." >&2
  exit 1
fi

if ! grep -q "get_supervisor_log_paths" "$TAURI_DIR/src/main.rs"; then
  echo "Missing Tauri supervisor log path command scaffold." >&2
  exit 1
fi

if grep -R "shell\|Command::new\|std::process::Command" "$TAURI_DIR/src" >/tmp/ai_workspace_tauri_shell_grep.$$ 2>/dev/null; then
  # Allow comments mentioning shell/commands, but fail only if actual process execution APIs appear.
  if grep -R "std::process::Command\|Command::new" "$TAURI_DIR/src" >/dev/null 2>&1; then
    rm -f /tmp/ai_workspace_tauri_shell_grep.$$
    echo "Unsafe process execution API found in Tauri scaffold." >&2
    exit 1
  fi
fi
rm -f /tmp/ai_workspace_tauri_shell_grep.$$

cat <<MSG
Tauri shell scaffold looks ready.

Checked:
- frontend/src-tauri/tauri.conf.json
- frontend/src-tauri/Cargo.toml
- frontend/src-tauri/build.rs
- frontend/src-tauri/src/main.rs
- frontend/package.json
- backend/requirements.txt

This script does not install Rust/Tauri, start backend, run scans, run MCP, or download models.
Next packaging step: replace the read-only supervisor bridge scaffold with app-owned backend process startup after runtime bundling strategy is stable.
MSG
