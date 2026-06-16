from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_app_owned_backend_health_readiness_uses_http_health_gate() -> None:
    response = client.get("/runtime/app-owned-backend-health-readiness")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] in {"health_readiness_gate_ready", "blocked"}
    assert payload["readiness_mode"] == "http_get_health_must_return_200"
    assert payload["health_url"] == "http://127.0.0.1:8000/health"
    assert payload["check_script"] == "scripts/check_tauri_backend_health_readiness.sh"
    assert any(item["id"] == "http-health-check" for item in payload["implementation_items"])
    assert any("open TCP port" in rule for rule in payload["safety_rules"])
    assert any("/health returns HTTP 200" in rule for rule in payload["safety_rules"])
    assert any(
        command["command"] == "scripts/check_tauri_backend_health_readiness.sh"
        for command in payload["validation_commands"]
    )


def test_app_owned_backend_health_readiness_route_is_documented_in_openapi() -> None:
    assert "/runtime/app-owned-backend-health-readiness" in app.openapi()["paths"]
