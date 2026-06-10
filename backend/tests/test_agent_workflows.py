from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _create_workspace() -> str:
    response = client.post(
        "/workspaces",
        json={
            "name": "Agent Workflow Project",
            "project_path": "/tmp/agent-workflow-project",
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_track_and_archive_agent_workflow() -> None:
    workspace_id = _create_workspace()

    create_response = client.post(
        f"/workspaces/{workspace_id}/agent-workflows",
        json={
            "goal": "Inspect CI, propose deployment checks, then re-check the result.",
            "provider": "ollama",
            "model": "llama3.2",
        },
    )

    assert create_response.status_code == 200
    workflow = create_response.json()
    assert workflow["workspace_id"] == workspace_id
    assert workflow["total_steps_count"] >= 4
    assert workflow["progress_percent"] == 0
    assert "Automatic shell execution" in workflow["unsupported_actions"]

    step_id = workflow["steps"][0]["id"]
    update_response = client.patch(
        f"/workspaces/{workspace_id}/agent-workflows/{workflow['id']}/steps/{step_id}",
        json={"status": "done", "notes": "Reviewed manually."},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["completed_steps_count"] == 1
    assert updated["progress_percent"] > 0
    assert updated["steps"][0]["notes"] == "Reviewed manually."

    list_response = client.get(f"/workspaces/{workspace_id}/agent-workflows")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [workflow["id"]]

    archive_response = client.patch(
        f"/workspaces/{workspace_id}/agent-workflows/{workflow['id']}/archive",
        json={"archived": True},
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["is_archived"] is True

    hidden_response = client.get(f"/workspaces/{workspace_id}/agent-workflows")
    assert hidden_response.status_code == 200
    assert hidden_response.json()["items"] == []

    archived_response = client.get(
        f"/workspaces/{workspace_id}/agent-workflows?include_archived=true"
    )
    assert archived_response.status_code == 200
    assert [item["id"] for item in archived_response.json()["items"]] == [workflow["id"]]
