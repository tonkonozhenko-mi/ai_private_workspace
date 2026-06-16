from fastapi.testclient import TestClient

from app.main import app


def test_frozen_backend_smoke_contract_is_manual_and_safe():
    client = TestClient(app)

    response = client.get("/runtime/frozen-backend-smoke-contract")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Frozen backend smoke contract"
    assert payload["status"] == "smoke_contract_ready"
    assert payload["smoke_script"] == "scripts/smoke_frozen_backend_runtime.sh"
    assert payload["smoke_mode"] == "developer_only_explicit_command"
    assert any(item["id"] == "smoke-script" for item in payload["items"])
    assert any(
        command["command"] == "scripts/smoke_frozen_backend_runtime.sh"
        for command in payload["validation_commands"]
    )
    assert any("developer-only" in rule for rule in payload["safety_rules"])
    assert any("must stop only the PID it started" in rule for rule in payload["safety_rules"])
    assert any(
        "Frontend and React still cannot execute shell commands" in rule
        for rule in payload["safety_rules"]
    )
