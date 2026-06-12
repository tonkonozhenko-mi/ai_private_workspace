#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
TAURI_LIB="$ROOT_DIR/frontend/src-tauri/src/lib.rs"
CARGO_TOML="$ROOT_DIR/frontend/src-tauri/Cargo.toml"
PACKAGE_LOCK="$ROOT_DIR/frontend/package-lock.json"
BLOCKERS=0
REVIEWS=0

fail() { echo "❌ $1" >&2; BLOCKERS=$((BLOCKERS + 1)); }
review() { echo "⚠️  $1" >&2; REVIEWS=$((REVIEWS + 1)); }
ok() { echo "✅ $1"; }

[ -f "$CARGO_TOML" ] && ok "Cargo.toml found" || fail "Missing frontend/src-tauri/Cargo.toml"
[ -f "$TAURI_MAIN" ] && ok "Tauri main.rs found" || fail "Missing frontend/src-tauri/src/main.rs"
[ -f "$TAURI_LIB" ] && ok "Tauri lib.rs found" || fail "Missing frontend/src-tauri/src/lib.rs required by Cargo [lib] ai_private_workspace_lib"

if [ -f "$TAURI_MAIN" ]; then
  grep -Fq 'ai_private_workspace_lib::run();' "$TAURI_MAIN" && ok "main.rs delegates to ai_private_workspace_lib::run" || fail "main.rs must only delegate to ai_private_workspace_lib::run()"
fi

if [ -f "$TAURI_LIB" ]; then
  grep -Fq 'pub fn run()' "$TAURI_LIB" && ok "lib.rs exposes pub fn run" || fail "lib.rs must expose pub fn run()"
  grep -Fq 'start_app_owned_backend_runtime' "$TAURI_LIB" && ok "lib.rs contains app-owned backend startup command" || fail "lib.rs missing start_app_owned_backend_runtime"
  grep -Fq 'GET /health HTTP/1.1' "$TAURI_LIB" && ok "lib.rs contains HTTP /health readiness gate" || fail "lib.rs missing HTTP /health readiness gate"
  grep -Fq 'AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json' "$TAURI_LIB" && ok "lib.rs contains frozen runtime manifest gate" || fail "lib.rs missing frozen runtime manifest gate"
  if grep -Fq 'tauri_plugin_opener' "$TAURI_LIB" && ! grep -Fq 'tauri-plugin-opener' "$CARGO_TOML"; then
    fail "lib.rs references tauri_plugin_opener but Cargo.toml does not declare tauri-plugin-opener"
  else
    ok "No undeclared tauri_plugin_opener usage"
  fi
fi

if [ -f "$PACKAGE_LOCK" ]; then
  if grep -E 'applied-caas|internal\.api\.openai|artifactory' "$PACKAGE_LOCK" >/dev/null; then
    fail "frontend/package-lock.json contains internal registry URLs; regenerate with npm config set registry https://registry.npmjs.org/ && rm package-lock.json && npm install"
  else
    ok "package-lock does not contain internal registry URLs"
  fi
else
  review "frontend/package-lock.json is missing; run cd frontend && npm install before npm ci based checks"
fi

if command -v cargo >/dev/null 2>&1; then
  ok "cargo is available"
else
  review "cargo is not available in this environment; run cargo check locally on the developer machine"
fi

printf '\nTauri Rust structure and registry check: %s blockers, %s review items\n' "$BLOCKERS" "$REVIEWS"
[ "$BLOCKERS" -eq 0 ]
