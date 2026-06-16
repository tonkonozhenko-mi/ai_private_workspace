from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_desktop_supervisor_contract_is_read_only_and_safe():
    response = client.get("/runtime/desktop-supervisor-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "contract-ready"
    assert body["default_backend_port"] == 8000
    assert body["health_endpoint"] == "http://127.0.0.1:8000/health"
    assert body["supervisor_script"] == "scripts/desktop_supervisor_contract.sh"
    assert any(rule["title"] == "Never kill by port" for rule in body["port_rules"])
    assert any("Frontend never executes shell commands" in rule for rule in body["safety_rules"])
    assert any("No scan, index, rebuild" in rule for rule in body["safety_rules"])
    assert any(stream["id"] == "backend" for stream in body["log_streams"])


def test_desktop_supervisor_contract_has_user_facing_startup_states():
    response = client.get("/runtime/desktop-supervisor-contract")

    assert response.status_code == 200
    states = response.json()["startup_states"]
    state_ids = [state["id"] for state in states]
    assert state_ids == [
        "preflight",
        "starting-backend",
        "waiting-health",
        "ready",
        "failed",
    ]
    assert all(state["user_message"] for state in states)
    assert all(state["technical_behavior"] for state in states)
