from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_app_owned_backend_startup_gate_is_safe_and_metadata_only() -> None:
    response = client.get("/runtime/app-owned-backend-startup-gate")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "startup_gate_ready"
    assert payload["startup_mode"] == "gate_metadata_only_no_process_start"
    assert payload["check_script"] == "scripts/check_tauri_app_owned_startup_gate.sh"
    assert any("frozen" in item["id"] for item in payload["required_gates"])
    assert any(
        "does not enable automatic backend startup" in rule for rule in payload["safety_rules"]
    )
    assert any("No kill-by-port" in rule for rule in payload["safety_rules"])


def test_app_owned_backend_startup_gate_route_is_documented_in_openapi() -> None:
    assert "/runtime/app-owned-backend-startup-gate" in app.openapi()["paths"]
