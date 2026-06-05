from pathlib import Path

from fastapi.testclient import TestClient

from app.core.domain.project_scan import ProjectFile
from app.core.domain.skill_registry import SkillRegistry
from app.main import app


client = TestClient(app)


def test_project_scan_detects_terragrunt_hcl(tmp_path) -> None:
    _write_text(tmp_path / "terragrunt.hcl", "inputs = {}\n")

    response = client.post("/projects/scan", json={"project_path": str(tmp_path)})

    assert response.status_code == 200
    files_by_path = {
        project_file["path"]: project_file for project_file in response.json()["files"]
    }
    assert files_by_path["terragrunt.hcl"]["detected_type"] == "terragrunt"


def test_skill_registry_returns_terragrunt_devops_skill() -> None:
    skills = SkillRegistry().detect_skills(
        [
            ProjectFile(
                path="terragrunt.hcl",
                extension=".hcl",
                size_bytes=10,
                detected_type="terragrunt",
            )
        ]
    )

    assert skills[0].name == "Terragrunt"
    assert skills[0].category == "devops"
    assert skills[0].confidence == "high"


def test_terragrunt_analysis_detects_static_structure(tmp_path) -> None:
    _write_text(
        tmp_path / "terragrunt.hcl",
        """
        remote_state {
          backend = "s3"
        }

        include {
          path = find_in_parent_folders()
        }

        dependency "vpc" {
          config_path = "../vpc"
        }

        inputs = {
          region = "us-east-1"
        }

        terraform {
          source = "git::ssh://example.com/infrastructure.git//modules/app"
        }
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/terragrunt")

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["total_terragrunt_files"] == 1
    assert result["files"] == ["terragrunt.hcl"]
    assert result["has_remote_state"] is True
    assert result["has_include_blocks"] is True
    assert result["has_dependencies"] is True
    assert result["has_inputs"] is True
    assert result["has_terraform_source"] is True
    findings_by_id = {finding["id"]: finding for finding in result["findings"]}
    assert findings_by_id["terragrunt_dependencies_detected"]["severity"] == "info"
    assert findings_by_id["terragrunt_inputs_detected"]["evidence"] == ["terragrunt.hcl"]
    assert findings_by_id["terragrunt_terraform_source_detected"]["evidence"] == [
        "terragrunt.hcl"
    ]


def test_terragrunt_missing_remote_state_produces_medium_finding(tmp_path) -> None:
    _write_text(
        tmp_path / "terragrunt.hcl",
        """
        include {
          path = find_in_parent_folders()
        }
        inputs = {}
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/terragrunt")

    assert response.status_code == 200
    findings_by_id = {finding["id"]: finding for finding in response.json()["findings"]}
    assert findings_by_id["terragrunt_remote_state_missing"]["severity"] == "medium"
    assert findings_by_id["terragrunt_remote_state_missing"]["evidence"] == [
        "terragrunt.hcl"
    ]


def test_workspace_summary_suggests_terragrunt_analysis(tmp_path) -> None:
    _write_text(tmp_path / "terragrunt.hcl", "remote_state {}\n")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert response.status_code == 200
    action_ids = {action["id"] for action in response.json()["suggested_actions"]}
    assert "analyze_terragrunt" in action_ids


def test_terragrunt_analysis_requires_scan_first(tmp_path) -> None:
    _write_text(tmp_path / "terragrunt.hcl", "inputs = {}\n")
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/analysis/terragrunt")

    assert response.status_code == 400
    assert response.json()["detail"] == "Project scan required before analysis"


def test_terragrunt_analysis_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/analysis/terragrunt")

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
