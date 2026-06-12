from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_desktop_packaging_design_locks_two_click_target() -> None:
    response = client.get("/runtime/desktop-packaging-design")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "locked"
    assert body["chosen_shell"] == "Tauri first"
    assert "double-click" in " ".join(body["user_experience"]).lower()
    assert any(decision["id"] == "backend-supervisor" for decision in body["decisions"])
    assert any(phase["id"] == "phase-2-macos" for phase in body["phases"])
    assert any("Frontend never executes shell commands" in rule for rule in body["safety_rules"])
    assert any("Silent model downloads" in item for item in body["not_in_scope_now"])
