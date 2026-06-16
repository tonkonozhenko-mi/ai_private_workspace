from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_v01_handoff_route_does_not_crash_settings() -> None:
    response = client.get("/runtime/v0.1-handoff")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "release-candidate"
    assert payload["validation_commands"]
    assert payload["validation_commands"][0]["label"]


def test_app_owned_backend_startup_implementation_is_manifest_gated() -> None:
    response = client.get("/runtime/app-owned-backend-startup-implementation")
    assert response.status_code == 200
    payload = response.json()

    assert payload["startup_mode"] == "real_tauri_process_start_gated_by_frozen_manifest"
    assert payload["check_script"] == "scripts/check_tauri_app_owned_backend_startup.sh"
    assert "start_app_owned_backend_runtime" in payload["tauri_commands"]
    assert "stop_app_owned_backend_runtime" in payload["tauri_commands"]
    assert any(
        "React/frontend still does not execute shell" in rule for rule in payload["safety_rules"]
    )
    assert any(item["id"] == "frozen-manifest" for item in payload["implementation_items"])


def test_app_owned_backend_startup_implementation_route_is_documented_in_openapi() -> None:
    assert "/runtime/app-owned-backend-startup-implementation" in app.openapi()["paths"]
