from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_v01_ui_smoke_check_is_manual_and_safety_focused() -> None:
    response = client.get("/runtime/v0.1-ui-smoke-check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual-check-required"
    assert "10-15" in payload["estimated_duration"]
    assert any(item["id"] == "models" for item in payload["checklist"])
    assert any(item["id"] == "settings" for item in payload["checklist"])
    assert any("No model download starts" in forbidden for item in payload["checklist"] for forbidden in item["must_not_happen"])
    assert any("Frontend executes" in condition for condition in payload["fail_fast_conditions"])
    assert "does not inspect browser state" in payload["safety_note"]


def test_v01_ui_smoke_check_route_is_documented_in_openapi() -> None:
    assert "/runtime/v0.1-ui-smoke-check" in app.openapi()["paths"]
