from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analysis_summary_without_scan_returns_scan_first_step(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/analysis/summary")

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["has_scan"] is False
    assert result["analyzers"] == []
    assert result["severity_counts"] == {"info": 0, "low": 0, "medium": 0, "high": 0}
    assert result["total_findings"] == 0
    assert result["top_findings"] == []
    assert result["recommended_next_steps"] == ["Run project scan first."]


def test_analysis_summary_aggregates_relevant_analyzers(tmp_path) -> None:
    _write_text(tmp_path / "main.tf", 'provider "aws" {}')
    _write_text(
        tmp_path / "terragrunt.hcl",
        """
        include {
          path = find_in_parent_folders()
        }

        inputs = {
          region = "us-east-1"
        }
        """,
    )
    _write_text(tmp_path / ".gitlab-ci.yml", "stages:\n  - test\ninvalid: [\n")
    _write_text(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
        name: CI
        on: [push]
        jobs:
          test:
            runs-on: ubuntu-latest
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/summary")

    assert response.status_code == 200
    result = response.json()
    analyzers_by_name = {analyzer["name"]: analyzer for analyzer in result["analyzers"]}
    assert result["has_scan"] is True
    assert analyzers_by_name["Terraform"]["status"] == "completed"
    assert analyzers_by_name["Terraform"]["findings_count"] == 3
    assert analyzers_by_name["Terragrunt"]["status"] == "completed"
    assert analyzers_by_name["GitLab CI"]["status"] == "completed"
    assert analyzers_by_name["GitHub Actions"]["status"] == "completed"
    assert result["severity_counts"] == {"info": 1, "low": 2, "medium": 3, "high": 1}
    assert result["total_findings"] == 7
    assert result["top_findings"][0]["severity"] == "high"
    assert result["top_findings"][0]["id"] == "gitlab_ci_yaml_parse_error"
    severities = [finding["severity"] for finding in result["top_findings"]]
    assert severities == ["high", "medium", "medium", "medium", "low", "low", "info"]
    assert "Review high severity findings first." in result["recommended_next_steps"]
    assert (
        "Review medium severity findings and decide whether they require changes."
        in result["recommended_next_steps"]
    )
    assert (
        "Review infrastructure configuration and state management."
        in result["recommended_next_steps"]
    )
    assert "Review CI/CD workflow structure and permissions." in result["recommended_next_steps"]


def test_analysis_summary_skips_irrelevant_analyzers(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Example")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/summary")

    assert response.status_code == 200
    result = response.json()
    assert result["has_scan"] is True
    assert all(analyzer["status"] == "skipped" for analyzer in result["analyzers"])
    assert result["total_findings"] == 0
    assert result["recommended_next_steps"] == [
        "No deterministic issues found. Consider generating an AI-assisted project overview."
    ]


def test_analysis_summary_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/analysis/summary")

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
