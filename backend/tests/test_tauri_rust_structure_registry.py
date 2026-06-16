from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_tauri_rust_structure_registry_endpoint() -> None:
    response = client.get("/runtime/tauri-rust-structure-registry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["check_script"] == "scripts/check_tauri_rust_structure_and_registry.sh"
    assert payload["rust_entrypoint"] == "frontend/src-tauri/src/lib.rs"
    assert payload["rust_library"] == "frontend/src-tauri/src/lib.rs"
    assert "internal" in payload["npm_registry_policy"]
    item_ids = {item["id"] for item in payload["validation_items"]}
    assert {
        "cargo-library-contract",
        "thin-main-entrypoint",
        "supervisor-library",
        "public-npm-lockfile",
    }.issubset(item_ids)
    assert any(
        command["command"] == "scripts/check_tauri_rust_structure_and_registry.sh"
        for command in payload["validation_commands"]
    )


def test_tauri_main_is_thin_and_library_owns_commands() -> None:
    main_rs = (ROOT / "frontend" / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    lib_rs = (ROOT / "frontend" / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")

    assert "ai_private_workspace_lib::run();" in main_rs
    assert "pub fn run()" in lib_rs
    assert "start_app_owned_backend_runtime" in lib_rs
    assert "GET /health HTTP/1.1" in lib_rs
    assert "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" in lib_rs
    assert "tauri_plugin_opener" not in lib_rs


def test_frontend_lockfile_does_not_contain_internal_registry_urls() -> None:
    lockfile = (ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8")

    forbidden = ["applied-caas", "internal.api.openai", "artifactory"]
    assert not any(token in lockfile for token in forbidden)
