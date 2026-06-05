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


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
