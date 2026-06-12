#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CARGO_TOML="$ROOT_DIR/frontend/src-tauri/Cargo.toml"
CARGO_LOCK="$ROOT_DIR/frontend/src-tauri/Cargo.lock"
GITIGNORE="$ROOT_DIR/.gitignore"
BLOCKERS=0
REVIEWS=0

fail() { echo "❌ $1" >&2; BLOCKERS=$((BLOCKERS + 1)); }
review() { echo "⚠️  $1" >&2; REVIEWS=$((REVIEWS + 1)); }
ok() { echo "✅ $1"; }

[ -f "$CARGO_TOML" ] && ok "Cargo.toml found" || fail "Missing frontend/src-tauri/Cargo.toml"

if [ -f "$CARGO_TOML" ]; then
  grep -Fq 'time = "=0.3.36"' "$CARGO_TOML" \
    && ok "Cargo.toml pins time to =0.3.36 for cookie compatibility" \
    || fail "Cargo.toml must pin time = \"=0.3.36\" until cookie/time conflict is resolved"

  grep -Fq 'tauri = { version = "2"' "$CARGO_TOML" \
    && ok "Tauri v2 dependency is declared" \
    || fail "Cargo.toml must keep the Tauri v2 dependency declared"
fi

if [ -f "$CARGO_LOCK" ]; then
  if grep -A2 'name = "time"' "$CARGO_LOCK" | grep -Fq 'version = "0.3.48"'; then
    review "Cargo.lock still has time 0.3.48; run: cd frontend && cargo update --manifest-path src-tauri/Cargo.toml -p time --precise 0.3.36"
  else
    ok "Cargo.lock does not pin the known-bad time 0.3.48 version"
  fi
else
  review "Cargo.lock is missing; cargo check will generate it locally"
fi

if [ -f "$GITIGNORE" ]; then
  grep -Fq 'frontend/src-tauri/target/' "$GITIGNORE" \
    && ok ".gitignore excludes frontend/src-tauri/target" \
    || fail ".gitignore must exclude frontend/src-tauri/target/"
fi

printf '\nTauri Rust dependency pin check: %s blockers, %s review items\n' "$BLOCKERS" "$REVIEWS"
[ "$BLOCKERS" -eq 0 ]
