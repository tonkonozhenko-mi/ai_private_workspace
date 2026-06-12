from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_bootstrap_creates_workspace_and_returns_initial_wizard_state(tmp_path) -> None:
    response = _bootstrap_workspace(tmp_path)

    assert response.status_code == 201
    result = response.json()
    workspace = result["workspace"]
    assert workspace["name"] == "Bootstrap Project"
    assert workspace["project_path"] == str(tmp_path)
    assert workspace["assistant_mode"] == "devops"
    assert workspace["privacy_mode"] == "local_only"
    assert result["onboarding_plan"]["assistant_profile_id"] == "devops"
    assert result["onboarding_plan"]["laptop_profile_id"] == "balanced"
    assert result["setup_commands"]["commands"]
    assert result["runtime_setup_guide"]["overall_status"] == "needs_setup"
    assert result["readiness"]["status"] == "needs_setup"
    assert result["readiness"]["can_scan"] is True
    assert result["readiness"]["can_analyze"] is False
    assert result["readiness"]["can_index"] is False
    assert result["readiness"]["can_ask"] is False
    assert result["next_steps"] == [
        "Review runtime setup guide.",
        "Start required local runtimes if needed.",
        "Run project scan.",
        "Review detected skills.",
        "Index workspace context.",
        "Ask first workspace question.",
    ]

    persisted = client.get(f"/workspaces/{workspace['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == workspace


def test_bootstrap_adds_workspace_created_timeline_event(tmp_path) -> None:
    result = _bootstrap_workspace(tmp_path).json()

    response = client.get(f"/workspaces/{result['workspace']['id']}/timeline")

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "workspace_created"
    assert events[0]["metadata"]["project_path"] == str(tmp_path)


def test_bootstrap_does_not_scan_index_or_create_commands(tmp_path) -> None:
    result = _bootstrap_workspace(tmp_path).json()
    workspace_id = result["workspace"]["id"]

    scan_response = client.get(f"/workspaces/{workspace_id}/scan")
    index_status_response = client.get(f"/workspaces/{workspace_id}/index/status")
    commands_response = client.get(f"/workspaces/{workspace_id}/commands")

    assert scan_response.status_code == 404
    assert index_status_response.status_code == 200
    assert index_status_response.json()["status"] == "not_indexed"
    assert commands_response.status_code == 200
    assert commands_response.json() == []


def test_invalid_assistant_profile_does_not_create_workspace(tmp_path) -> None:
    before_ids = _workspace_ids()

    response = _bootstrap_workspace(tmp_path, assistant_profile_id="missing-profile")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown assistant profile: missing-profile"
    assert _workspace_ids() == before_ids


def test_invalid_laptop_profile_does_not_create_workspace(tmp_path) -> None:
    before_ids = _workspace_ids()

    response = _bootstrap_workspace(tmp_path, laptop_profile_id="missing-laptop")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown laptop profile: missing-laptop"
    assert _workspace_ids() == before_ids


def _bootstrap_workspace(
    project_path,
    assistant_profile_id: str = "devops",
    laptop_profile_id: str = "balanced",
):
    return client.post(
        "/onboarding/bootstrap-workspace",
        json={
            "name": "Bootstrap Project",
            "project_path": str(project_path),
            "assistant_profile_id": assistant_profile_id,
            "laptop_profile_id": laptop_profile_id,
            "privacy_mode": "local_only",
            "container_runtime": "podman",
        },
    )


def _workspace_ids() -> set[str]:
    response = client.get("/workspaces")
    assert response.status_code == 200
    return {workspace["id"] for workspace in response.json()}
