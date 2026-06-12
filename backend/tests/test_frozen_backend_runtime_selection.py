from fastapi.testclient import TestClient

from app.main import app


def test_frozen_backend_runtime_selection_is_read_only_and_safe():
    client = TestClient(app)

    response = client.get("/runtime/frozen-backend-runtime-selection")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Frozen backend runtime selection"
    assert payload["status"] == "selection_contract_ready"
    assert payload["check_script"] == "scripts/check_tauri_runtime_selection.sh"
    assert any(candidate["id"] == "frozen-pyinstaller-runtime" for candidate in payload["candidates"])
    assert any(candidate["id"] == "staged-source-runtime" for candidate in payload["candidates"])
    assert any("backend_start_enabled remains false" in rule for rule in payload["safety_rules"])
    assert any(command["command"] == "scripts/check_tauri_runtime_selection.sh" for command in payload["validation_commands"])
