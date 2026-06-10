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


def test_agent_workflow_approval_gate_blocks_done_until_approved() -> None:
    workspace_id = _create_workspace()

    create_response = client.post(
        f"/workspaces/{workspace_id}/agent-workflows",
        json={
            "goal": "Inspect files, propose a safe command, then verify the result.",
            "provider": "ollama",
            "model": "llama3.2",
        },
    )
    assert create_response.status_code == 200
    workflow = create_response.json()
    step = next(item for item in workflow["steps"] if item["requires_user_confirmation"])
    assert step["approval_status"] == "pending"
    assert workflow["pending_approval_steps_count"] >= 1

    blocked_response = client.patch(
        f"/workspaces/{workspace_id}/agent-workflows/{workflow['id']}/steps/{step['id']}",
        json={"status": "done"},
    )
    assert blocked_response.status_code == 400
    assert "approved" in blocked_response.json()["detail"]

    preview_response = client.post(
        f"/workspaces/{workspace_id}/agent-workflows/{workflow['id']}/steps/{step['id']}/approval-preview",
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["step_id"] == step["id"]
    assert "Automatic shell execution" in preview["blocked_actions"]
    assert preview["safety_note"].startswith("Approval records user intent")

    approval_response = client.patch(
        f"/workspaces/{workspace_id}/agent-workflows/{workflow['id']}/steps/{step['id']}/approval",
        json={"approval_status": "approved", "approval_note": "Reviewed manually."},
    )
    assert approval_response.status_code == 200
    approved = approval_response.json()
    approved_step = next(item for item in approved["steps"] if item["id"] == step["id"])
    assert approved_step["approval_status"] == "approved"
    assert approved["approved_steps_count"] >= 1

    done_response = client.patch(
        f"/workspaces/{workspace_id}/agent-workflows/{workflow['id']}/steps/{step['id']}",
        json={"status": "done", "notes": "Manual result checked."},
    )
    assert done_response.status_code == 200
    assert next(item for item in done_response.json()["steps"] if item["id"] == step["id"])["status"] == "done"
