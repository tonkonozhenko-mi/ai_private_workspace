from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_v01_publication_handoff_is_final_publish_path_and_safety_focused() -> None:
    response = client.get("/runtime/v0.1-publication-handoff")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready-after-local-smoke-check"
    assert "Phase 21" in payload["current_position"]
    assert "0-1" in payload["v01_remaining_work"]
    assert "15-25" in payload["v1_remaining_work"]
    assert payload["source_archive_name"] == "build/release/ai-private-workspace-v0.1-source.zip"
    assert any(step["id"] == "ui-smoke" for step in payload["steps"])
    assert any("git status --short" == step["command"] for step in payload["steps"])
    assert any("frontend/node_modules" in item for item in payload["do_not_commit"])
    assert any("Frontend must never execute shell commands" in rule for rule in payload["safety_rules"])


def test_v01_publication_handoff_route_is_documented_in_openapi() -> None:
    assert "/runtime/v0.1-publication-handoff" in app.openapi()["paths"]
