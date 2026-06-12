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

# Use the current working tree instead of git archive so the script is useful before
# the release commit exists. Excludes mirror the runtime/build policy in .gitignore.
zip -r "$ARCHIVE_PATH" . \
  -x './.git/*' \
  -x './backend/.ai-workbench/*' \
  -x './backend/.venv/*' \
  -x './frontend/node_modules/*' \
  -x './frontend/dist/*' \
  -x './frontend/.vite/*' \
  -x './frontend/src-tauri/target/*' \
  -x './build/*' \
  -x './.pytest_cache/*' \
  -x './.venv/*' \
  -x './*.db' \
  -x './*.sqlite' \
  -x './*.sqlite3' \
  -x '*/__pycache__/*' \
  -x '*/.pytest_cache/*' \
  -x '*/.venv/*' \
  -x '*.pyc' \
  -x '*.tsbuildinfo' \
  -x '.DS_Store'

printf 'Source release archive created: %s\n' "$ARCHIVE_PATH"
printf 'Archive is a build artifact. Do not commit build/release/.\n'
