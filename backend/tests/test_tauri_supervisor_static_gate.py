from fastapi.testclient import TestClient

from app.main import app


def test_tauri_supervisor_static_gate_contract() -> None:
    client = TestClient(app)

    response = client.get("/runtime/tauri-supervisor-static-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["check_script"] == "scripts/check_tauri_supervisor_bridge.sh"
    item_ids = {item["id"] for item in payload["items"]}
    assert "status-command" in item_ids
    assert "log-path-command" in item_ids
    assert "preflight-command" in item_ids
    assert "backend-start-gated" in item_ids
    assert "no-generic-shell-api" in item_ids
    assert any("app-owned" in rule.lower() for rule in payload["safety_rules"])
    assert any(
        "scan" in rule.lower() and "model downloads" in rule.lower()
        for rule in payload["safety_rules"]
    )
