#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ICONS_DIR="$ROOT_DIR/frontend/src-tauri/icons"
LIB_RS="$ROOT_DIR/frontend/src-tauri/src/lib.rs"
BLOCKERS=0
REVIEWS=0

fail() { echo "❌ $1" >&2; BLOCKERS=$((BLOCKERS + 1)); }
review() { echo "⚠️  $1" >&2; REVIEWS=$((REVIEWS + 1)); }
ok() { echo "✅ $1"; }

[ -d "$ICONS_DIR" ] && ok "Tauri icons directory exists" || fail "Missing frontend/src-tauri/icons"

python3 - "$ICONS_DIR" <<'PY' || BLOCKERS=$((BLOCKERS + 1))
from pathlib import Path
import struct
import sys

icons_dir = Path(sys.argv[1])
required = {
    "icon.png": (512, 512),
    "32x32.png": (32, 32),
    "128x128.png": (128, 128),
    "128x128@2x.png": (256, 256),
}
failed = False

for name, expected_size in required.items():
    path = icons_dir / name
    if not path.exists():
        print(f"❌ Missing {path}", file=sys.stderr)
        failed = True
        continue
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        print(f"❌ {path} is not a PNG file", file=sys.stderr)
        failed = True
        continue
    if data[12:16] != b"IHDR":
        print(f"❌ {path} has invalid PNG IHDR", file=sys.stderr)
        failed = True
        continue
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    if (width, height) != expected_size:
        print(f"❌ {path} size is {width}x{height}, expected {expected_size[0]}x{expected_size[1]}", file=sys.stderr)
        failed = True
    if bit_depth != 8 or color_type != 6:
        print(f"❌ {path} must be 8-bit RGBA PNG; got bit_depth={bit_depth}, color_type={color_type}", file=sys.stderr)
        failed = True
    if not failed:
        pass

if failed:
    raise SystemExit(1)
print("✅ Required Tauri icons are present as 8-bit RGBA PNG files")
PY

if [ -f "$LIB_RS" ]; then
  if grep -Fq 'use std::path::{Path, PathBuf};' "$LIB_RS"; then
    fail "frontend/src-tauri/src/lib.rs still imports unused Path"
  else
    ok "Tauri lib.rs does not import unused Path"
  fi
else
  fail "Missing frontend/src-tauri/src/lib.rs"
fi

if command -v cargo >/dev/null 2>&1; then
  ok "cargo is available; run: cd frontend && cargo check --manifest-path src-tauri/Cargo.toml"
else
  review "cargo is not available in this environment; verify cargo check locally on macOS"
fi

printf '\nTauri icon asset check: %s blockers, %s review items\n' "$BLOCKERS" "$REVIEWS"
[ "$BLOCKERS" -eq 0 ]
