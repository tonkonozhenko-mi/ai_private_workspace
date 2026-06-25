#!/usr/bin/env bash
# Fetch a prebuilt llama.cpp `llama-server` binary (+ its shared libraries) for
# one OS/arch and stage it for bundling into the app. This runs at BUILD time
# (CI/release), never on an end user's machine — users get the binary already
# inside the installed app and download only small model files.
#
# Usage: scripts/fetch_llama_server.sh <arm64|x64>
# The OS is auto-detected: macOS, Windows (run under Git Bash on the runner), or
# Linux. Optional env: LLAMA_CPP_VERSION (release tag, e.g. b9789; "latest"
# tracks newest). GITHUB_TOKEN is used when present to avoid API rate limits.
set -euo pipefail

ARCH="${1:-}"
if [ "$ARCH" != "arm64" ] && [ "$ARCH" != "x64" ]; then
  echo "usage: $0 <arm64|x64>" >&2
  exit 2
fi

# A Python interpreter is used for JSON parsing and (on Windows) zip extraction.
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "python is required" >&2; exit 2; }

# Detect the platform. Under Git Bash on a Windows runner, `uname -s` reports
# MINGW64_NT-… / MSYS_NT-… — both mean Windows.
case "$(uname -s)" in
  Darwin) OS=macos ;;
  MINGW* | MSYS* | CYGWIN* | Windows_NT) OS=windows ;;
  *) OS=linux ;;
esac

REPO="ggml-org/llama.cpp"
# Pinned for reproducible builds. Bump deliberately to update; override with the
# LLAMA_CPP_VERSION env var, or set it to "latest" to track the newest release.
VERSION="${LLAMA_CPP_VERSION:-b9789}"
DEST="build/desktop/llama-runtime/${ARCH}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Per-OS asset name suffix, binary name, and shared-library glob.
#   macOS:   llama-<tag>-bin-macos-<arch>.tar.gz   → llama-server   + *.dylib
#   Windows: llama-<tag>-bin-win-cpu-<arch>.zip     → llama-server.exe + *.dll
#   Linux:   llama-<tag>-bin-ubuntu-<arch>.tar.gz  → llama-server   + *.so*
case "$OS" in
  macos)   NEEDLE="bin-macos-${ARCH}.tar.gz";   BIN="llama-server";     LIBGLOB="*.dylib" ;;
  windows) NEEDLE="bin-win-cpu-${ARCH}.zip";    BIN="llama-server.exe"; LIBGLOB="*.dll" ;;
  linux)   NEEDLE="bin-ubuntu-${ARCH}.tar.gz";  BIN="llama-server";     LIBGLOB="*.so*" ;;
esac

if [ "$VERSION" = "latest" ]; then
  API="https://api.github.com/repos/${REPO}/releases/latest"
else
  API="https://api.github.com/repos/${REPO}/releases/tags/${VERSION}"
fi

echo "Resolving llama.cpp release (${VERSION}) for ${OS}-${ARCH}…"
if [ -n "${GITHUB_TOKEN:-}" ]; then
  RELEASE_JSON="$(curl -fsSL -H "Authorization: Bearer ${GITHUB_TOKEN}" "$API")"
else
  RELEASE_JSON="$(curl -fsSL "$API")"
fi
ASSET_URL="$(printf '%s' "$RELEASE_JSON" | "$PY" -c "
import json, sys
data = json.load(sys.stdin)
needle = '${NEEDLE}'
for asset in data.get('assets', []):
    if asset.get('name', '').endswith(needle):
        print(asset['browser_download_url']); break
")"

if [ -z "$ASSET_URL" ]; then
  echo "No ${OS}-${ARCH} asset (…${NEEDLE}) found in release ${VERSION}." >&2
  exit 1
fi

echo "Downloading $ASSET_URL"
mkdir -p "$TMP/unpack"
case "$NEEDLE" in
  *.tar.gz)
    curl -fSL "$ASSET_URL" -o "$TMP/llama.tar.gz"
    tar -xzf "$TMP/llama.tar.gz" -C "$TMP/unpack"
    ;;
  *.zip)
    curl -fSL "$ASSET_URL" -o "$TMP/llama.zip"
    # Use Python's zipfile so extraction works the same on every runner (no
    # dependency on `unzip` being installed under Git Bash on Windows).
    "$PY" -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
      "$TMP/llama.zip" "$TMP/unpack"
    ;;
esac

# The archive nests binaries under bin/ (and sometimes libs under a sibling
# lib/); collect llama-server and every shared library it needs into a flat
# staging dir so the binary finds them next to itself.
SERVER_BIN="$(find "$TMP/unpack" -type f -name "$BIN" | head -n1)"
if [ -z "$SERVER_BIN" ]; then
  echo "$BIN not found inside the downloaded archive." >&2
  exit 1
fi
rm -rf "$DEST"
mkdir -p "$DEST"
cp -L "$SERVER_BIN" "$DEST/" 2>/dev/null || cp "$SERVER_BIN" "$DEST/"

# Copy EVERY shared library from the extracted tree. Do NOT restrict by depth:
# release archives ship a versioned real file plus unversioned symlink aliases,
# and the binary loads via the alias name, so both must be materialized. `cp -L`
# dereferences symlinks into real files under their own name (Windows DLLs are
# plain files, so the fallback `cp` covers them too).
find "$TMP/unpack" -name "$LIBGLOB" 2>/dev/null | while IFS= read -r lib; do
  cp -L "$lib" "$DEST/$(basename "$lib")" 2>/dev/null \
    || cp "$lib" "$DEST/$(basename "$lib")" 2>/dev/null || true
done

# Executable bit only means something on Unix; Windows ignores it.
[ "$OS" = "windows" ] || chmod +x "$DEST/$BIN"

echo "Staged $BIN for ${OS}-${ARCH} at ${DEST}:"
ls -1 "$DEST"
