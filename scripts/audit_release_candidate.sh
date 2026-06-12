#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$(pwd)}"
cd "$ROOT_DIR"

failures=0
warn() { printf 'WARN: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; failures=$((failures + 1)); }
pass() { printf 'PASS: %s\n' "$1"; }

required_paths=(
  backend
  frontend
  docs
  scripts
  pytest.ini
  .gitignore
  README.md
  CONTRIBUTING.md
  SECURITY.md
  .editorconfig
  .gitattributes
  .github
  .github/workflows/ci.yml
  .github/workflows/desktop-packaging-checks.yml
  .github/pull_request_template.md
  .github/ISSUE_TEMPLATE/bug_report.yml
  .github/ISSUE_TEMPLATE/feature_request.yml
)

for path in "${required_paths[@]}"; do
  if [ -e "$path" ]; then pass "required path exists: $path"; else fail "missing required path: $path"; fi
done

local_artifacts=(
  backend/.ai-workbench
  build
  frontend/node_modules
  frontend/dist
  .pytest_cache
  backend/.venv
  frontend/.vite
)

for path in "${local_artifacts[@]}"; do
  if [ -e "$path" ]; then warn "runtime/build path present locally, exclude from release zip: $path"; else pass "release zip excludes local artifact path: $path"; fi
done

# Runtime databases are allowed only inside ignored runtime/build folders. A source-tree
# database outside those folders would be easy to publish accidentally, so it fails audit.
if find . \( \
  -path './.git' -o \
  -path './backend/.ai-workbench' -o \
  -path './frontend/node_modules' -o \
  -path './frontend/dist' -o \
  -path './build' -o \
  -path './.pytest_cache' \
\) -prune -o \( \
  -name '*.db' -o \
  -name '*.sqlite' -o \
  -name '*.sqlite3' \
\) -print | grep -q .; then
  fail "database files found outside ignored runtime/build paths; remove them from source or release archive"
else
  pass "no source-tree *.db, *.sqlite, or *.sqlite3 files found outside ignored runtime/build paths"
fi


if [ -f frontend/package-lock.json ]; then
  if grep -E "applied-caas|internal\.api\.openai|artifactory" frontend/package-lock.json >/dev/null; then
    fail "frontend/package-lock.json contains internal registry URLs; regenerate it with the public npm registry"
  else
    pass "frontend/package-lock.json contains no internal registry URLs"
  fi
fi

# TypeScript incremental build metadata is local-only. It is harmless locally, but
# should not be committed or included in handoff/source archives.
if find . \( \
  -path './.git' -o \
  -path './frontend/node_modules' -o \
  -path './frontend/dist' -o \
  -path './build' \
\) -prune -o -name '*.tsbuildinfo' -print | grep -q .; then
  warn "TypeScript build metadata found locally; exclude from release zip: *.tsbuildinfo"
else
  pass "release zip excludes TypeScript build metadata: *.tsbuildinfo"
fi

release_docs=(
  docs/START_HERE.md
  docs/ROADMAP.md
  docs/API_INVENTORY.md
  docs/PROJECT_CHECKPOINT.md
  docs/DESKTOP_PACKAGING_DESIGN_LOCK.md
  docs/WINDOWS_PACKAGING_FOUNDATION.md
  docs/V01_DEMO_HANDOFF.md
  docs/V01_RELEASE_NOTES.md
  docs/V1_PRODUCT_COMPLETION_ROADMAP.md
  docs/GITHUB_PUBLICATION_CHECKLIST.md
  docs/SOURCE_RELEASE_CHECKLIST.md
  docs/RELEASE_CANDIDATE_AUDIT.md
  docs/assets/product-flow.svg
)

for doc in "${release_docs[@]}"; do
  if [ -f "$doc" ]; then pass "release doc exists: $doc"; else fail "missing release doc: $doc"; fi
done

shell_scripts=(
  scripts/apply_generated_update.sh
  scripts/package_macos_app_foundation.sh
  scripts/prepare_tauri_shell_scaffold.sh
  scripts/prepare_windows_packaging_foundation.sh
  scripts/prepare_source_release_archive.sh
  scripts/audit_release_candidate.sh
  scripts/check_tauri_rust_structure_and_registry.sh
)

for script in "${shell_scripts[@]}"; do
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

if grep -R "AI Workbench\|Private Project AI Workbench" README.md docs frontend/src backend/app 2>/dev/null | grep -v "legacy" | grep -v "Legacy" | grep -q .; then
  warn "legacy Workbench wording still appears in non-legacy context; review product-facing naming"
else
  pass "product-facing naming uses AI Private Workspace"
fi

if [ "$failures" -gt 0 ]; then
  printf '\nRelease candidate audit failed with %s issue(s).\n' "$failures"
  exit 1
fi

printf '\nRelease candidate audit passed with warnings allowed.\n'
