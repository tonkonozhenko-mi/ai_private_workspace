#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$(pwd)}"
cd "$ROOT_DIR"

failures=0
warn() { printf 'WARN: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; failures=$((failures + 1)); }
pass() { printf 'PASS: %s\n' "$1"; }

for path in backend frontend docs scripts pytest.ini .gitignore README.md .github; do
  if [ -e "$path" ]; then pass "required path exists: $path"; else fail "missing required path: $path"; fi
done

for path in backend/.ai-workbench build frontend/node_modules frontend/dist .pytest_cache; do
  if [ -e "$path" ]; then warn "runtime/build path present locally, exclude from release zip: $path"; else pass "release zip excludes local artifact path: $path"; fi
done

if find . -path './.git' -prune -o \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -print | grep -q .; then
  fail "database files found in source tree; remove them from release archive"
else
  pass "no *.db, *.sqlite, or *.sqlite3 files found"
fi

for doc in docs/START_HERE.md docs/ROADMAP.md docs/API_INVENTORY.md docs/PROJECT_CHECKPOINT.md docs/DESKTOP_PACKAGING_DESIGN_LOCK.md docs/WINDOWS_PACKAGING_FOUNDATION.md docs/V1_PRODUCT_COMPLETION_ROADMAP.md docs/GITHUB_PUBLICATION_CHECKLIST.md; do
  if [ -f "$doc" ]; then pass "release doc exists: $doc"; else fail "missing release doc: $doc"; fi
done

for script in scripts/apply_generated_update.sh scripts/package_macos_app_foundation.sh scripts/prepare_tauri_shell_scaffold.sh scripts/prepare_windows_packaging_foundation.sh scripts/prepare_source_release_archive.sh; do
  if [ -f "$script" ]; then
    bash -n "$script" && pass "script syntax ok: $script"
  else
    fail "missing script: $script"
  fi
done

if grep -R "shell commands" frontend/src >/dev/null 2>&1; then
  pass "frontend wording keeps shell execution visible as safety concept"
else
  warn "could not find frontend safety wording about shell commands"
fi

if [ "$failures" -gt 0 ]; then
  printf '\nRelease candidate audit failed with %s issue(s).\n' "$failures"
  exit 1
fi

printf '\nRelease candidate audit passed with warnings allowed.\n'
