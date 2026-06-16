from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_v01_release_gate_is_clear_about_go_no_go_and_v1_gap() -> None:
    response = client.get("/runtime/v0.1-release-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "v0.1-source-rc-release-gate"
    assert "Phase 21" in payload["current_position"]
    assert "0-1" in payload["source_rc_remaining_tasks"]
    assert "15-25" in payload["v1_remaining_large_tasks"]
    assert any(item["id"] == "audit" for item in payload["release_gate_items"])
    assert any(
        item["id"] == "ui-smoke" and item["status"] == "recommended"
        for item in payload["release_gate_items"]
    )
    assert "Go only" in payload["go_no_go_rule"]
    assert any("Frontend must not execute shell" in rule for rule in payload["safety_rules"])


def test_v01_release_gate_route_is_documented_in_openapi() -> None:
    assert "/runtime/v0.1-release-gate" in app.openapi()["paths"]
