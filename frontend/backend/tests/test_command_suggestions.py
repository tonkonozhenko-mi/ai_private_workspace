from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_workspace_without_scan_returns_empty_suggestions(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/commands/suggestions")

    assert response.status_code == 200
    assert response.json() == []


def test_workspace_with_detected_skills_returns_relevant_suggestions(tmp_path) -> None:
    _write_text(tmp_path / "main.tf", 'provider "aws" {}')
    _write_text(tmp_path / "terragrunt.hcl", "inputs = {}\n")
    _write_text(tmp_path / ".gitlab-ci.yml", "stages:\n  - test\n")
    _write_text(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
    )
    _write_text(tmp_path / "app.py", "print('hello')\n")
    _write_text(tmp_path / "Dockerfile", "FROM python:3.12-slim\n")
    _write_text(tmp_path / "chart" / "Chart.yaml", "apiVersion: v2\nname: example\n")
    _write_text(
        tmp_path / "chart" / "templates" / "deployment.yaml",
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: example\n",
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/commands/suggestions")

    assert response.status_code == 200
    suggestions = response.json()
    commands = {suggestion["command"] for suggestion in suggestions}
    suggestions_by_command = {
        suggestion["command"]: suggestion for suggestion in suggestions
    }
    assert len(suggestions) == 12
    assert {
        "git status",
        "git diff",
        "git log --oneline -n 10",
        "terraform validate",
        "terraform plan",
        "terragrunt validate",
        "helm lint .",
        "kubectl kustomize .",
        'grep -n "stage:" .gitlab-ci.yml',
        'grep -R "uses:" .github/workflows',
        "python -m pytest",
        "docker build --dry-run .",
    }.issubset(commands)
    assert all(suggestion["requires_approval"] is True for suggestion in suggestions)
    assert suggestions_by_command["git status"]["risk"] == "readonly"
    assert suggestions_by_command["terraform validate"]["risk"] == "readonly"
    assert suggestions_by_command["docker build --dry-run ."]["risk"] == "unknown"
    assert suggestions_by_command["kubectl kustomize ."]["risk"] == "unknown"
    assert suggestions_by_command['grep -R "uses:" .github/workflows']["risk"] == "readonly"

    commands_response = client.get(f"/workspaces/{workspace['id']}/commands")
    assert commands_response.status_code == 200
    assert commands_response.json() == []


def test_command_suggestions_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/commands/suggestions")

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
