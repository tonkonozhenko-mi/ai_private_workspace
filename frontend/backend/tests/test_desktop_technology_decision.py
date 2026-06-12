from fastapi.testclient import TestClient

from app.main import app


def test_desktop_technology_decision_is_reviewable() -> None:
    client = TestClient(app)

    response = client.get("/runtime/desktop-technology-decision")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "reviewable"
    assert payload["current_candidate"] == "Tauri-first desktop shell"
    assert "replaceable" in payload["decision_state"]
    option_ids = {option["id"] for option in payload["alternatives"]}
    assert {"tauri", "electron", "native", "browser_plus_launcher"}.issubset(option_ids)
    assert any("Frontend must never" in rule for rule in payload["decision_guardrails"])
    assert any("model downloads" in rule for rule in payload["decision_guardrails"])
    assert any("Windows" in step for step in payload["next_steps"])
