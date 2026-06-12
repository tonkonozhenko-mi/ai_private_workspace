from fastapi.testclient import TestClient

from app.main import app


def test_desktop_runtime_readiness_exposes_phase_22_plan() -> None:
    client = TestClient(app)

    response = client.get("/runtime/desktop-runtime-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "phase-22-ready-to-start"
    assert "Phase 22" in payload["current_phase"]
    assert "v0.1" in payload["v01_position"]
    assert "5-8" in payload["honest_remaining_work"]
    assert "15-25" in payload["honest_remaining_work"]
    assert len(payload["readiness_items"]) >= 6
    item_ids = {item["id"] for item in payload["readiness_items"]}
    assert {"runtime-manifest", "tauri-shell", "supervisor-contract", "persistent-jobs"}.issubset(item_ids)
    assert any(command["command"] == "scripts/prepare_tauri_shell_scaffold.sh" for command in payload["validation_commands"])
    assert any("Frontend React code must never execute shell commands" == rule for rule in payload["safety_rules"])
    assert any("scan" in rule and "model downloads" in rule for rule in payload["safety_rules"])
