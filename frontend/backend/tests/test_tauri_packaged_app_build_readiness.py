from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_tauri_packaged_app_build_readiness_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/runtime/tauri-packaged-app-build-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["check_script"] == "scripts/check_tauri_packaged_app_build.sh"
    assert payload["packaged_build_command"] == "cd frontend && npm run tauri:build"
    assert any(item["id"] == "frozen-runtime-resource" for item in payload["readiness_items"])
    assert any("/health" in rule for rule in payload["safety_rules"])


def test_tauri_packaged_app_build_source_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    tauri_conf = (root / "frontend/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    lib_rs = (root / "frontend/src-tauri/src/lib.rs").read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert '"active": true' in tauri_conf
    assert '../../build/desktop/frozen-backend-runtime' in tauri_conf
    assert '"icon": [' in tauri_conf
    assert "../Resources/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" in lib_rs
    assert "GET /health HTTP/1.1" in lib_rs
    assert "frontend/src-tauri/target/" in gitignore
    assert ".idea/" in gitignore
    assert ".DS_Store" in gitignore
