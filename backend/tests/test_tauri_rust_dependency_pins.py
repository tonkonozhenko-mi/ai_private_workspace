from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_tauri_rust_dependency_pins_endpoint() -> None:
    response = client.get("/runtime/tauri-rust-dependency-pins")

    assert response.status_code == 200
    payload = response.json()
    assert payload["check_script"] == "scripts/check_tauri_rust_dependency_pins.sh"
    assert "time" in payload["cargo_toml_policy"]
    item_ids = {item["id"] for item in payload["validation_items"]}
    assert {
        "time-cookie-compatibility-pin",
        "cargo-lock-refresh",
        "tauri-target-gitignore",
    }.issubset(item_ids)


def test_cargo_toml_pins_time_for_cookie_compatibility() -> None:
    cargo_toml = (ROOT / "frontend" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")

    assert 'time = "=0.3.36"' in cargo_toml


def test_gitignore_excludes_tauri_target() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "frontend/src-tauri/target/" in gitignore


def test_source_release_archive_excludes_tauri_target() -> None:
    script = (ROOT / "scripts" / "prepare_source_release_archive.sh").read_text(encoding="utf-8")

    assert "frontend/src-tauri/target" in script
