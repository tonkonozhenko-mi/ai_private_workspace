#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_JSON="$ROOT_DIR/frontend/package.json"
PACKAGE_LOCK="$ROOT_DIR/frontend/package-lock.json"

blockers=0

check_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -Fq "$pattern" "$file"; then
    echo "✅ $label"
  else
    echo "❌ $label"
    blockers=$((blockers + 1))
  fi
}

check_not_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -Fq "$pattern" "$file"; then
    echo "❌ $label"
    blockers=$((blockers + 1))
  else
    echo "✅ $label"
  fi
}

echo "AI Private Workspace npm supply-chain policy check"
echo "Project root: $ROOT_DIR"
echo

[[ -f "$PACKAGE_JSON" ]] || { echo "❌ frontend/package.json is missing"; exit 1; }
[[ -f "$PACKAGE_LOCK" ]] || { echo "❌ frontend/package-lock.json is missing"; exit 1; }

check_contains "$PACKAGE_JSON" '"allowScripts"' "package.json has an explicit npm allowScripts policy"
check_contains "$PACKAGE_JSON" '"esbuild": true' "esbuild postinstall is explicitly approved"
check_contains "$PACKAGE_JSON" '"fsevents": true' "fsevents optional install script is explicitly approved"
check_not_contains "$PACKAGE_LOCK" "packages.applied-caas-gateway" "package-lock does not reference internal OpenAI registry"
check_not_contains "$PACKAGE_LOCK" "internal.api.openai" "package-lock does not reference internal OpenAI hosts"
check_not_contains "$PACKAGE_LOCK" "artifactory" "package-lock does not reference internal Artifactory URLs"

echo
echo "Summary: ${blockers} blocker(s)"
[[ "$blockers" -eq 0 ]]
