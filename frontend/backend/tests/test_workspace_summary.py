from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_workspace_without_scan_returns_scan_project_action(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["workspace_id"] == workspace["id"]
    assert summary["has_scan"] is False
    assert summary["detected_skills_count"] == 0
    assert summary["detected_skills"] == []
    assert summary["suggested_actions"] == [
        {
            "id": "scan_project",
            "title": "Scan project",
            "description": "Scan the workspace project to detect files and skills.",
            "category": "setup",
            "priority": "high",
        }
    ]
    assert summary["command_activity"] == {
        "total_commands": 0,
        "pending_commands": 0,
        "approved_commands": 0,
        "rejected_commands": 0,
        "executed_commands": 0,
        "failed_commands": 0,
        "last_command_id": None,
        "last_command_status": None,
        "last_command": None,
    }


def test_workspace_with_scan_returns_skill_based_actions(tmp_path) -> None:
    _write_text(tmp_path / "main.tf", 'resource "null_resource" "example" {}')
    _write_text(tmp_path / "app.py", "print('hello')")
    _write_text(tmp_path / ".gitlab-ci.yml", "stages:\n  - test\n")
    workspace = _create_workspace(tmp_path)

    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert response.status_code == 200
    summary = response.json()
    action_ids = {action["id"] for action in summary["suggested_actions"]}
    skill_names = {skill["name"] for skill in summary["detected_skills"]}
    assert summary["has_scan"] is True
    assert {"Terraform", "GitLab CI", "Python"}.issubset(skill_names)
    assert {
        "generate_project_overview",
        "analyze_terraform",
        "analyze_cicd",
        "analyze_python",
    }.issubset(action_ids)


def test_workspace_summary_suggested_actions_are_limited(tmp_path) -> None:
    _write_text(tmp_path / "main.tf", 'resource "null_resource" "example" {}')
    _write_text(tmp_path / "app.py", "print('hello')")
    _write_text(tmp_path / "Dockerfile", "FROM python:3.12-slim")
    _write_text(tmp_path / ".gitlab-ci.yml", "stages:\n  - test\n")
    _write_text(tmp_path / "README.md", "# Example Project")
    _write_text(tmp_path / "chart" / "Chart.yaml", "apiVersion: v2\nname: example\n")
    _write_text(
        tmp_path / "chart" / "templates" / "deployment.yaml",
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: example\n",
    )
    workspace = _create_workspace(tmp_path)

    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert response.status_code == 200
    assert len(response.json()["suggested_actions"]) == 6


def test_workspace_summary_includes_command_activity(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    executed_command = _propose_command(workspace["id"], tmp_path, "git status")
    rejected_command = _propose_command(workspace["id"], tmp_path, "git diff")
    approved_command = _propose_command(workspace["id"], tmp_path, "git log")
    pending_command = _propose_command(workspace["id"], tmp_path, "git branch")

    approve_response = client.post(f"/commands/{executed_command['id']}/approve")
    assert approve_response.status_code == 200
    execute_response = client.post(f"/commands/{executed_command['id']}/execute")
    assert execute_response.status_code == 200

    reject_response = client.post(f"/commands/{rejected_command['id']}/reject")
    assert reject_response.status_code == 200

    approve_only_response = client.post(f"/commands/{approved_command['id']}/approve")
    assert approve_only_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert response.status_code == 200
    activity = response.json()["command_activity"]
    assert activity["total_commands"] == 4
    assert activity["pending_commands"] == 1
    assert activity["approved_commands"] == 1
    assert activity["rejected_commands"] == 1
    assert activity["executed_commands"] == 1
    assert activity["failed_commands"] == 0
    assert activity["last_command_id"] == pending_command["id"]
    assert activity["last_command_status"] == "pending"
    assert activity["last_command"] == "git branch"


def test_workspace_summary_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/summary")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


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


def _propose_command(workspace_id: str, cwd: Path, command: str) -> dict:
    response = client.post(
        f"/workspaces/{workspace_id}/commands",
        json={
            "command": command,
            "cwd": str(cwd),
            "reason": "Check command activity",
        },
    )

    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
