from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]


def test_tauri_dev_smoke_readiness_endpoint_records_local_success():
    client = TestClient(app)

    response = client.get("/runtime/tauri-dev-smoke-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["local_success_reported"] is True
    assert payload["milestone"] == "Task 256 — Tauri dev smoke success recorded"
    assert payload["check_script"] == "scripts/check_tauri_dev_smoke_readiness.sh"
    assert any(item["id"] == "tauri-dev" and item["status"] == "ok" for item in payload["readiness_items"])
    assert any("npm run tauri dev" in command["command"] for command in payload["validation_commands"])
    assert any("not start scan" in rule for rule in payload["safety_rules"])


def test_tauri_dev_smoke_readiness_script_exists_and_checks_guardrails():
    script = ROOT / "scripts" / "check_tauri_dev_smoke_readiness.sh"

    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "frontend/src-tauri/target/" in text
    assert "GET /health HTTP/1.1" in text
    assert "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" in text
    assert "packages.applied-caas-gateway" in text
    assert "cargo --version" in text


def test_tauri_dev_smoke_readiness_source_hygiene():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    lib_rs = (ROOT / "frontend" / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    main_rs = (ROOT / "frontend" / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")

    assert "frontend/src-tauri/target/" in gitignore
    assert "ai_private_workspace_lib::run();" in main_rs
    assert "start_app_owned_backend_runtime" in lib_rs
    assert "GET /health HTTP/1.1" in lib_rs
