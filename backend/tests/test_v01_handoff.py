from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_v01_handoff_endpoint_is_read_only_demo_guide() -> None:
    response = client.get("/runtime/v0.1-handoff")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "release-candidate"
    assert payload["github_ready"] is True
    assert payload["release_label"] == "v0.1 local-first release candidate"
    assert len(payload["demo_steps"]) >= 8
    assert any(step["id"] == "agent" for step in payload["demo_steps"])
    assert any(file["path"] == "README.md" for file in payload["important_files"])
    assert any("Frontend never executes shell" in rule for rule in payload["safety_rules"])
    assert any("audit_release_candidate" in command["command"] for command in payload["validation_commands"])


def test_v01_handoff_route_is_documented_in_openapi() -> None:
    assert "/runtime/v0.1-handoff" in app.openapi()["paths"]
