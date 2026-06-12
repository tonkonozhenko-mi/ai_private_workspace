from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_tauri_supervisor_bridge_endpoint_is_safe_and_read_only() -> None:
    response = client.get("/runtime/tauri-supervisor-bridge")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "foundation"
    assert payload["bridge_file"] == "frontend/src-tauri/src/lib.rs"
    assert any(state["id"] == "wait-health" for state in payload["startup_states"])
    assert any(command["name"] == "get_supervisor_status" for command in payload["tauri_commands"])
    assert any("React frontend never executes shell commands" in rule for rule in payload["safety_rules"])
    assert any("No scan, index" in rule for rule in payload["safety_rules"])
    assert "not a signed installer" in " ".join(payload["known_limitations"])


def test_tauri_supervisor_bridge_is_documented_in_openapi() -> None:
    assert "/runtime/tauri-supervisor-bridge" in app.openapi()["paths"]
