#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI="$ROOT_DIR/frontend/src-tauri/src/lib.rs"
ENTRYPOINT="$ROOT_DIR/backend/packaging/pyinstaller_backend_entrypoint.py"
DEPS="$ROOT_DIR/backend/app/api/dependencies.py"
SETTINGS="$ROOT_DIR/backend/app/config/settings.py"
SQLITE_STORE="$ROOT_DIR/backend/app/adapters/vector_store/sqlite_vector_store.py"
ASK_USE_CASE="$ROOT_DIR/backend/app/core/use_cases/ask_workspace_question.py"

failures=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'BLOCKER: %s\n' "$1"; failures=$((failures + 1)); }

require_text() {
  local file="$1"
  local text="$2"
  local label="$3"
  if grep -Fq "$text" "$file"; then
    pass "$label"
  else
    fail "$label"
  fi
}

reject_text() {
  local file="$1"
  local text="$2"
  local label="$3"
  if grep -Fq "$text" "$file"; then
    fail "$label"
  else
    pass "$label"
  fi
}

require_text "$TAURI" '.env("VECTOR_STORE", "sqlite")' "packaged Tauri backend uses persistent sqlite vector store"
require_text "$TAURI" '.env("VECTOR_STORE_PATH", vector_store_path())' "Tauri passes app-owned vector store path"
require_text "$TAURI" 'app_data_dir().join("data").join("vector_store.db")' "Tauri vector store path lives under app data/data"
require_text "$TAURI" 'VECTOR_STORE=sqlite' "backend log includes persistent vector store provider"
require_text "$TAURI" 'VECTOR_STORE_PATH={}' "backend log includes vector store path"

require_text "$ENTRYPOINT" 'os.environ.setdefault("VECTOR_STORE", "sqlite")' "frozen entrypoint defaults to persistent sqlite vector store"
require_text "$ENTRYPOINT" 'os.environ["VECTOR_STORE_PATH"] = str(vector_store_path)' "frozen entrypoint exports vector store path"
require_text "$ENTRYPOINT" 'default=app_data_dir / "data" / "vector_store.db"' "frozen vector store path is app-owned"

require_text "$DEPS" 'SQLiteVectorStore' "sqlite vector store is registered in dependencies"
require_text "$DEPS" 'if vector_store_type == "sqlite"' "VECTOR_STORE=sqlite is supported"
require_text "$SETTINGS" 'AI_WORKSPACE_VECTOR_STORE_PATH' "legacy vector store path alias is supported"
require_text "$SQLITE_STORE" 'CREATE TABLE IF NOT EXISTS workspace_vector_chunks' "persistent chunks table exists"
require_text "$SQLITE_STORE" 'ON CONFLICT(workspace_id, chunk_id) DO UPDATE' "reindex upserts chunks without duplicates"
require_text "$ASK_USE_CASE" 'index_metadata_exists_but_no_chunks_found' "missing persisted chunks diagnostic remains explicit"

reject_text "$TAURI" 'VECTOR_STORE=memory' "packaged Tauri does not log memory vector store"
reject_text "$TAURI" 'pkill' "no pkill in Tauri supervisor"
reject_text "$TAURI" 'killall' "no killall in Tauri supervisor"
reject_text "$TAURI" 'taskkill' "no taskkill in Tauri supervisor"
reject_text "$TAURI" 'lsof -ti' "no kill-by-port in Tauri supervisor"
reject_text "$ENTRYPOINT" '.app/Contents/Resources' "frozen backend does not write inside app bundle"

if [[ "$failures" -ne 0 ]]; then
  printf '\nPersistent RAG packaged contracts failed: %s blocker(s).\n' "$failures"
  exit 1
fi

printf '\nPersistent RAG packaged contracts passed.\n'
