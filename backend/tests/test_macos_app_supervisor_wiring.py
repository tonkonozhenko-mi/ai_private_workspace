from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_macos_app_supervisor_wiring_contract_is_read_only_and_safe() -> None:
    response = client.get("/runtime/macos-app-supervisor-wiring")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "wired-foundation"
    assert payload["build_script"] == "scripts/package_macos_app_foundation.sh"
    assert payload["backend_health_url"] == "http://127.0.0.1:8000/health"
    assert "AI Private Workspace.app" in payload["app_bundle_path"]
    assert any("/health" in step["summary"] for step in payload["startup_flow"])
    assert any("refuses to kill" in rule for rule in payload["supervisor_guarantees"])
    assert any("No scan" in rule for rule in payload["supervisor_guarantees"])
    assert any("backend.log" in file["path"] for file in payload["generated_files"])


def test_macos_app_supervisor_wiring_documents_limitations() -> None:
    response = client.get("/runtime/macos-app-supervisor-wiring")

    assert response.status_code == 200
    payload = response.json()
    assert any("not a signed" in item for item in payload["known_limitations"])
    assert any("Tauri" in item for item in payload["next_steps"])
