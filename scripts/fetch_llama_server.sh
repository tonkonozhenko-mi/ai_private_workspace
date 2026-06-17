#!/usr/bin/env bash
# Fetch a prebuilt llama.cpp `llama-server` binary (+ its dylibs) for one macOS
# architecture and stage it for bundling into the app. This runs at BUILD time
# (CI/release), never on an end user's machine — users get the binary already
# inside the signed .app and download only small model files.
#
# Usage: scripts/fetch_llama_server.sh <arm64|x64>
# Optional env: LLAMA_CPP_VERSION (release tag, e.g. b4404). Default: latest.
set -euo pipefail

ARCH="${1:-}"
if [ "$ARCH" != "arm64" ] && [ "$ARCH" != "x64" ]; then
  echo "usage: $0 <arm64|x64>" >&2
  exit 2
fi

REPO="ggml-org/llama.cpp"
# Pinned for reproducible builds. Bump deliberately to update; override with the
# LLAMA_CPP_VERSION env var, or set it to "latest" to track the newest release.
VERSION="${LLAMA_CPP_VERSION:-b9675}"
DEST="build/desktop/llama-runtime/${ARCH}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Resolve the download URL for the macOS asset matching this arch via the GitHub
# API (uses GITHUB_TOKEN when present to avoid rate limits). The asset is named
# like `llama-<tag>-bin-macos-<arch>.zip`.
if [ "$VERSION" = "latest" ]; then
  API="https://api.github.com/repos/${REPO}/releases/latest"
else
  API="https://api.github.com/repos/${REPO}/releases/tags/${VERSION}"
fi

echo "Resolving llama.cpp release (${VERSION}) for macos-${ARCH}…"
# No bash arrays here: macOS ships bash 3.2, where an empty "${arr[@]}" under
# `set -u` is an "unbound variable" error. Branch on the token instead.
if [ -n "${GITHUB_TOKEN:-}" ]; then
  RELEASE_JSON="$(curl -fsSL -H "Authorization: Bearer ${GITHUB_TOKEN}" "$API")"
else
  RELEASE_JSON="$(curl -fsSL "$API")"
fi
ASSET_URL="$(printf '%s' "$RELEASE_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
needle = 'bin-macos-${ARCH}.tar.gz'
for asset in data.get('assets', []):
    if asset.get('name', '').endswith(needle):
        print(asset['browser_download_url']); break
")"

if [ -z "$ASSET_URL" ]; then
  echo "No macos-${ARCH} asset found in release ${VERSION}." >&2
  exit 1
fi

echo "Downloading $ASSET_URL"
mkdir -p "$TMP/unzip"
curl -fSL "$ASSET_URL" -o "$TMP/llama.tar.gz"
tar -xzf "$TMP/llama.tar.gz" -C "$TMP/unzip"

# The archive puts binaries under build/bin (or similar); collect llama-server
# and every dylib it needs into a flat staging dir so the binary finds them.
SERVER_BIN="$(find "$TMP/unzip" -type f -name 'llama-server' | head -n1)"
if [ -z "$SERVER_BIN" ]; then
  echo "llama-server not found inside the downloaded archive." >&2
  exit 1
fi
rm -rf "$DEST"
mkdir -p "$DEST"
cp -L "$SERVER_BIN" "$DEST/"

# Copy EVERY dylib from the whole extracted tree (binaries live under bin/, but
# libraries are often in a sibling lib/). Do NOT restrict to -type f: release
# archives ship a versioned real file (libllama.0.0.9675.dylib) plus unversioned
# symlink aliases (libllama-common.0.dylib) — the binary loads via @rpath using
# the alias name, so the alias must be materialized too. `cp -L` dereferences
# each symlink into a real file under its own name, so both names end up present.
find "$TMP/unzip" -name '*.dylib' | while IFS= read -r dylib; do
  cp -L "$dylib" "$DEST/$(basename "$dylib")" 2>/dev/null || true
done
chmod +x "$DEST/llama-server"

echo "Staged llama-server for ${ARCH} at ${DEST}:"
ls -1 "$DEST"
