#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

required_files=(
  "frontend/src-tauri/tauri.conf.json"
  "frontend/src-tauri/Cargo.toml"
  "frontend/src-tauri/src/main.rs"
  "backend/app"
  "backend/requirements.txt"
  "scripts/windows_supervisor_contract.ps1"
  "scripts/package_windows_app_foundation.ps1"
)

for path in "${required_files[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Missing required Windows packaging resource: $path" >&2
    exit 1
  fi
done

grep -q "LOCALAPPDATA" scripts/windows_supervisor_contract.ps1
grep -q "Do not kill unknown processes" scripts/windows_supervisor_contract.ps1
grep -q "127.0.0.1" scripts/windows_supervisor_contract.ps1
grep -q "AI_PRIVATE_WORKSPACE_WINDOWS_PACKAGE_MANIFEST" scripts/package_windows_app_foundation.ps1
grep -q "Excluded runtime/build data" scripts/package_windows_app_foundation.ps1

echo "Windows packaging foundation validation passed."
echo "PowerShell scripts are source-controlled contracts; they are not executed by this validation helper."
