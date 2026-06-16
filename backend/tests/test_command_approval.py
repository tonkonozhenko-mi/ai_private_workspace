from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_command_repository import SQLiteCommandRepository
from app.core.domain.command import CommandProposal
from app.main import app

client = TestClient(app)


def test_propose_command_creates_pending_command(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _propose_command(workspace["id"], tmp_path, "git status")

    assert response.status_code == 201
    proposal = response.json()
    assert proposal["workspace_id"] == workspace["id"]
    assert proposal["command"] == "git status"
    assert proposal["cwd"] == str(tmp_path)
    assert proposal["reason"] == "Check repository state"
    assert proposal["risk"] == "readonly"
    assert proposal["status"] == "pending"
    assert proposal["policy_allowed"] is True
    assert proposal["policy_mode"] == "auto_executable"
    assert proposal["policy_reason"] == "Command is read-only and allowed by policy."
    assert proposal["created_at"]
    assert proposal["approved_at"] is None
    assert proposal["rejected_at"] is None
    assert proposal["executed_at"] is None
    assert proposal["stdout"] is None
    assert proposal["stderr"] is None
    assert proposal["exit_code"] is None


def test_approve_pending_command(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command = _propose_command(workspace["id"], tmp_path, "git status").json()

    response = client.post(f"/commands/{command['id']}/approve")

    assert response.status_code == 200
    proposal = response.json()
    assert proposal["status"] == "approved"
    assert proposal["approved_at"]


def test_reject_pending_command(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command = _propose_command(workspace["id"], tmp_path, "git status").json()

    response = client.post(f"/commands/{command['id']}/reject")

    assert response.status_code == 200
    proposal = response.json()
    assert proposal["status"] == "rejected"
    assert proposal["rejected_at"]


def test_cannot_approve_already_rejected_command(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command = _propose_command(workspace["id"], tmp_path, "git status").json()
    reject_response = client.post(f"/commands/{command['id']}/reject")
    assert reject_response.status_code == 200

    response = client.post(f"/commands/{command['id']}/approve")

    assert response.status_code == 400
    assert response.json()["detail"] == "Only pending commands can be approved"


def test_execute_approved_command_uses_fake_runner(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command = _propose_command(workspace["id"], tmp_path, "git status").json()
    approve_response = client.post(f"/commands/{command['id']}/approve")
    assert approve_response.status_code == 200

    response = client.post(f"/commands/{command['id']}/execute")

    assert response.status_code == 200
    proposal = response.json()
    assert proposal["status"] == "executed"
    assert proposal["executed_at"]
    assert proposal["stdout"] == "fake execution: git status"
    assert proposal["stderr"] == ""
    assert proposal["exit_code"] == 0


def test_execute_approved_policy_blocked_command_fails(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command = _propose_command(workspace["id"], tmp_path, "terraform apply").json()
    assert command["risk"] == "destructive"
    assert command["policy_allowed"] is False
    assert command["policy_mode"] == "blocked"
    approve_response = client.post(f"/commands/{command['id']}/approve")
    assert approve_response.status_code == 200

    response = client.post(f"/commands/{command['id']}/execute")

    assert response.status_code == 400
    assert response.json()["detail"] == "Destructive commands are blocked by policy."


def test_execute_approved_manual_only_command_fails(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command = _propose_command(
        workspace["id"],
        tmp_path,
        "python scripts/check.py",
    ).json()
    assert command["risk"] == "unknown"
    assert command["policy_allowed"] is False
    assert command["policy_mode"] == "manual_only"
    approve_response = client.post(f"/commands/{command['id']}/approve")
    assert approve_response.status_code == 200

    response = client.post(f"/commands/{command['id']}/execute")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Unknown-risk commands require manual execution outside the assistant."
    )


def test_cannot_execute_pending_command(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command = _propose_command(workspace["id"], tmp_path, "git status").json()

    response = client.post(f"/commands/{command['id']}/execute")

    assert response.status_code == 400
    assert response.json()["detail"] == "Only approved commands can be executed"


def test_list_workspace_commands(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    first_command = _propose_command(workspace["id"], tmp_path, "git status").json()
    second_command = _propose_command(workspace["id"], tmp_path, "terraform plan").json()

    response = client.get(f"/workspaces/{workspace['id']}/commands")

    assert response.status_code == 200
    command_ids = [proposal["id"] for proposal in response.json()]
    assert first_command["id"] in command_ids
    assert second_command["id"] in command_ids


def test_propose_command_unknown_workspace_returns_404(tmp_path) -> None:
    response = _propose_command("missing-workspace", tmp_path, "git status")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_list_commands_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/commands")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_unknown_command_returns_404() -> None:
    response = client.post("/commands/missing-command/approve")

    assert response.status_code == 404
    assert response.json()["detail"] == "Command not found"


def test_command_proposal_survives_sqlite_repository_recreation(tmp_path) -> None:
    db_path = tmp_path / "workspaces.db"
    repository = SQLiteCommandRepository(db_path)
    proposal = CommandProposal(
        id="command-1",
        workspace_id="workspace-1",
        command="git status",
        cwd="/tmp/project",
        reason="Check repository state",
        risk="readonly",
        status="pending",
        created_at="2026-01-01T00:00:00+00:00",
        approved_at=None,
        rejected_at=None,
        executed_at=None,
        stdout=None,
        stderr=None,
        exit_code=None,
    )

    repository.create(proposal)
    restarted_repository = SQLiteCommandRepository(db_path)

    assert restarted_repository.get(proposal.id) == proposal


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Example Workspace",
            "project_path": str(project_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _propose_command(
    workspace_id: str,
    cwd: Path,
    command: str,
):
    return client.post(
        f"/workspaces/{workspace_id}/commands",
        json={
            "command": command,
            "cwd": str(cwd),
            "reason": "Check repository state",
        },
    )
