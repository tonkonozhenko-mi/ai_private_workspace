#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$(pwd)}"
ARCHIVE_NAME="${2:-ai-private-workspace-v0.1-source.zip}"
RELEASE_DIR="$ROOT_DIR/build/release"
ARCHIVE_PATH="$RELEASE_DIR/$ARCHIVE_NAME"

cd "$ROOT_DIR"

if [ ! -d backend ] || [ ! -d frontend ] || [ ! -d docs ] || [ ! -d scripts ]; then
  echo "ERROR: run this script from the AI Private Workspace repository root." >&2
  exit 1
fi

./scripts/audit_release_candidate.sh

mkdir -p "$RELEASE_DIR"
rm -f "$ARCHIVE_PATH"

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git archive --format=zip --output="$ARCHIVE_PATH" HEAD
else
  zip -r "$ARCHIVE_PATH" . \
    -x './backend/.ai-workbench/*' \
    -x './frontend/node_modules/*' \
    -x './frontend/dist/*' \
    -x './build/*' \
    -x './.pytest_cache/*' \
    -x './.git/*' \
    -x './*.db' \
    -x './*.sqlite' \
    -x './*.sqlite3' \
    -x '*/__pycache__/*' \
    -x '*/.venv/*'
fi

printf 'Source release archive created: %s\n' "$ARCHIVE_PATH"
printf 'Archive is a build artifact. Do not commit build/release/.\n'
