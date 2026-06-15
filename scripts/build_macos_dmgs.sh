#!/usr/bin/env bash
#
# Build distributable macOS DMGs for both architectures:
#   - Apple Silicon (aarch64) — built natively
#   - Intel (x86_64)          — Rust shell is cross-compiled; the PyInstaller
#                               backend is built under Rosetta with an x86_64 venv
#
# Result: two DMGs in dist/, one per architecture. Users download the matching one.
#
# Usage:
#   ./scripts/build_macos_dmgs.sh            # build both
#   ./scripts/build_macos_dmgs.sh arm64      # only Apple Silicon
#   ./scripts/build_macos_dmgs.sh x86_64     # only Intel
#
# Must run on macOS. The Intel build needs Rosetta 2 (softwareupdate
# --install-rosetta) and the x86_64 Rust target (added automatically).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WHICH="${1:-both}"
DIST_DIR="$ROOT_DIR/dist"
ARM_VENV_PY="$ROOT_DIR/backend/.venv/bin/python"
X86_VENV="$ROOT_DIR/backend/.venv-x86_64"
X86_VENV_PY="$X86_VENV/bin/python"

VERSION="$(node -p "require('./frontend/package.json').version" 2>/dev/null || echo "0.0.0")"

run_step() { printf '\n▶ %s\n' "$1"; shift; "$@"; printf '✅ %s\n' "$1" 2>/dev/null || true; }

if [ "$(uname)" != "Darwin" ]; then
  echo "❌ This script must run on macOS." >&2
  exit 1
fi

mkdir -p "$DIST_DIR"

# --- Frontend is architecture-independent: build it once. -------------------
printf '\n▶ Build frontend\n'
( cd frontend && npm run typecheck && npm run build )
printf '✅ Frontend built\n'

# --- Helper: build one architecture end to end. -----------------------------
# $1 label (arm64|x86_64)  $2 rust triple  $3 packaging python  $4 rosetta prefix
build_arch () {
  local label="$1" triple="$2" py="$3" rosetta="$4"

  printf '\n========== Building %s (%s) ==========\n' "$label" "$triple"
  rustup target add "$triple" >/dev/null 2>&1 || true

  printf '\n▶ Build frozen backend (%s)\n' "$label"
  AI_PRIVATE_WORKSPACE_PACKAGING_PYTHON="$py" \
    ${rosetta} ./scripts/build_pyinstaller_backend_runtime.sh

  printf '\n▶ Build Tauri app + DMG (%s)\n' "$label"
  ( cd frontend && npm run tauri:build -- --target "$triple" )

  local dmg
  dmg="$(ls -t "frontend/src-tauri/target/$triple/release/bundle/dmg/"*.dmg 2>/dev/null | head -n1 || true)"
  if [ -z "$dmg" ]; then
    echo "❌ No DMG produced for $label at target/$triple/release/bundle/dmg/" >&2
    exit 1
  fi
  local out="$DIST_DIR/AI-Private-Workspace_${VERSION}_${label}.dmg"
  cp "$dmg" "$out"
  printf '✅ %s\n' "$out"
}

# --- Apple Silicon (native) -------------------------------------------------
build_apple_silicon () {
  local py="$ARM_VENV_PY"
  [ -x "$py" ] || py="python3"
  build_arch "arm64" "aarch64-apple-darwin" "$py" ""
}

# --- Intel (x86_64 backend under Rosetta, Rust cross-compiled) ---------------
build_intel () {
  if ! arch -x86_64 /usr/bin/true 2>/dev/null; then
    echo "❌ Rosetta 2 is required for the Intel build. Install it with:" >&2
    echo "   softwareupdate --install-rosetta --agree-to-license" >&2
    exit 1
  fi

  if [ ! -x "$X86_VENV_PY" ]; then
    printf '\n▶ Creating x86_64 packaging venv (under Rosetta)\n'
    arch -x86_64 /usr/bin/python3 -m venv "$X86_VENV"
    arch -x86_64 "$X86_VENV_PY" -m pip install --upgrade pip
    arch -x86_64 "$X86_VENV_PY" -m pip install -r backend/requirements.txt
  fi

  build_arch "x86_64" "x86_64-apple-darwin" "$X86_VENV_PY" "arch -x86_64"
}

case "$WHICH" in
  arm64|aarch64|silicon) build_apple_silicon ;;
  x86_64|x64|intel)      build_intel ;;
  both|all)              build_apple_silicon; build_intel ;;
  *) echo "Unknown arch '$WHICH' (use: arm64 | x86_64 | both)" >&2; exit 1 ;;
esac

printf '\n✅ Done. DMGs are in: %s\n' "$DIST_DIR"
ls -1 "$DIST_DIR"/*.dmg 2>/dev/null || true
