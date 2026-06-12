#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "AI Private Workspace daily-use desktop smoke"
echo "Project root: $ROOT_DIR"
echo

run_step() {
  local label="$1"
  shift
  echo "▶ $label"
  "$@"
  echo "✅ $label"
  echo
}

run_step "release audit" ./scripts/audit_release_candidate.sh
run_step "workspace API contract" ./scripts/check_packaged_app_workspace_api_smoke.sh
run_step "full packaged-flow contract" ./scripts/check_packaged_app_full_flow_contracts.sh
run_step "persistent RAG contract" ./scripts/check_packaged_app_persistent_rag_contracts.sh
run_step "runtime readiness UX contract" ./scripts/check_runtime_readiness_ux_contracts.sh
run_step "daily-use MVP contract" ./scripts/check_daily_use_mvp_contracts.sh
run_step "daily-use UI simplification contract" ./scripts/check_daily_use_ui_contracts.sh

run_step "backend tests" bash -lc 'cd backend && python3 -m pytest -q'
run_step "frontend install" bash -lc 'cd frontend && npm ci'
run_step "frontend typecheck" bash -lc 'cd frontend && npm run typecheck'
run_step "frontend build" bash -lc 'cd frontend && npm run build'
run_step "frozen backend runtime build" ./scripts/build_pyinstaller_backend_runtime.sh
run_step "frozen backend runtime check" ./scripts/check_pyinstaller_backend_runtime.sh
run_step "frozen backend runtime smoke" ./scripts/smoke_frozen_backend_runtime.sh
run_step "tauri cargo check" bash -lc 'cd frontend && cargo check --manifest-path src-tauri/Cargo.toml'
run_step "tauri app build" bash -lc 'cd frontend && npm run tauri:build'

echo "✅ Daily-use desktop smoke finished."
echo "Open the app:"
echo "open \"$ROOT_DIR/frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app\""
