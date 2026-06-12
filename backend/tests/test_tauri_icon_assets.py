from pathlib import Path
import struct

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def _png_header(path: Path) -> tuple[int, int, int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    return struct.unpack(">IIBB", data[16:26])


def test_tauri_icon_assets_endpoint() -> None:
    response = client.get("/runtime/tauri-icon-assets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["check_script"] == "scripts/check_tauri_icon_assets.sh"
    assert payload["status"] == "ready"
    item_ids = {item["id"] for item in payload["validation_items"]}
    assert {"icon-png", "32x32-png", "128x128-png", "128x128-2x-png", "rust-unused-path-import"} <= item_ids


def test_required_tauri_icons_are_rgba_png_files() -> None:
    icons = {
        "icon.png": (512, 512),
        "32x32.png": (32, 32),
        "128x128.png": (128, 128),
        "128x128@2x.png": (256, 256),
    }

    for name, expected_size in icons.items():
        width, height, bit_depth, color_type = _png_header(ROOT / "frontend" / "src-tauri" / "icons" / name)
        assert (width, height) == expected_size
        assert bit_depth == 8
        assert color_type == 6


def test_tauri_lib_does_not_import_unused_path() -> None:
    lib_rs = (ROOT / "frontend" / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")

    assert "use std::path::{Path, PathBuf};" not in lib_rs
    assert "use std::path::PathBuf;" in lib_rs


def test_tauri_icon_check_script_exists() -> None:
    script = ROOT / "scripts" / "check_tauri_icon_assets.sh"

    assert script.exists()
    assert "color_type != 6" in script.read_text(encoding="utf-8")
