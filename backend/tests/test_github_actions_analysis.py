from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_project_scan_detects_github_actions_workflow(tmp_path) -> None:
    _write_text(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "name: CI\non: [push]\njobs: {}\n",
    )

    response = client.post("/projects/scan", json={"project_path": str(tmp_path)})

    assert response.status_code == 200
    files_by_path = {
        project_file["path"]: project_file for project_file in response.json()["files"]
    }
    assert files_by_path[".github/workflows/ci.yml"]["detected_type"] == "github_actions"


def test_github_actions_analysis_detects_workflow_structure(tmp_path) -> None:
    _write_text(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
        name: CI

        on:
          push:
            branches:
              - main
          pull_request:

        permissions:
          contents: read

        jobs:
          test:
            runs-on: ubuntu-latest
            strategy:
              matrix:
                python-version: ["3.11", "3.12"]
            steps:
              - uses: actions/checkout@v4
              - run: echo "${{ secrets.API_TOKEN }}"

          deploy:
            uses: ./.github/workflows/deploy.yml
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    files_by_path = {
        project_file["path"]: project_file for project_file in scan_response.json()["files"]
    }
    assert files_by_path[".github/workflows/ci.yml"]["detected_type"] == "github_actions"

    response = client.get(f"/workspaces/{workspace['id']}/analysis/github-actions")

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["workflow_files_count"] == 1
    assert result["total_jobs_count"] == 2

    workflow = result["workflows"][0]
    assert workflow["path"] == ".github/workflows/ci.yml"
    assert workflow["name"] == "CI"
    assert workflow["triggers"] == ["push", "pull_request"]
    assert workflow["jobs_count"] == 2
    assert workflow["uses_matrix"] is True
    assert workflow["uses_permissions"] is True
    assert workflow["has_secrets_reference"] is True
    assert workflow["uses_reusable_workflows"] is True

    findings_by_id = {finding["id"]: finding for finding in result["findings"]}
    assert findings_by_id["github_actions_secrets_referenced"]["severity"] == "info"
    assert findings_by_id["github_actions_matrix_detected"]["evidence"] == [
        ".github/workflows/ci.yml"
    ]
    assert findings_by_id["github_actions_reusable_workflows_detected"]["severity"] == "info"


def test_workspace_summary_suggests_cicd_for_github_actions(tmp_path) -> None:
    _write_text(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert response.status_code == 200
    action_ids = {action["id"] for action in response.json()["suggested_actions"]}
    assert "analyze_cicd" in action_ids


def test_github_actions_invalid_yaml_returns_high_finding(tmp_path) -> None:
    _write_text(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "name: CI\non: [push]\njobs: [\n",
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/github-actions")

    assert response.status_code == 200
    result = response.json()
    assert result["workflow_files_count"] == 1
    assert result["workflows"] == []
    assert result["total_jobs_count"] == 0
    assert result["findings"][0]["id"] == "github_actions_yaml_parse_error"
    assert result["findings"][0]["severity"] == "high"
    assert result["findings"][0]["evidence"] == [".github/workflows/ci.yml"]


def test_github_actions_analysis_requires_scan_first(tmp_path) -> None:
    _write_text(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "name: CI\non: [push]\njobs: {}\n",
    )
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/analysis/github-actions")

    assert response.status_code == 400
    assert response.json()["detail"] == "Project scan required before analysis"


def test_github_actions_analysis_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/analysis/github-actions")

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
