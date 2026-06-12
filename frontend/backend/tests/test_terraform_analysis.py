from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_terraform_analysis_detects_static_structure(tmp_path) -> None:
    _write_text(
        tmp_path / "main.tf",
        """
        terraform {
          backend "s3" {}
        }

        provider "aws" {}

        variable "region" {}

        output "bucket_name" {
          value = "example"
        }

        module "network" {
          source = "./network"
        }
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/terraform")

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["project_path"] == str(tmp_path)
    assert result["total_terraform_files"] == 1
    assert result["files"] == ["main.tf"]
    assert result["has_backend_config"] is True
    assert result["has_provider_config"] is True
    assert result["has_variables"] is True
    assert result["has_outputs"] is True
    assert result["has_modules"] is True
    findings_by_id = {finding["id"]: finding for finding in result["findings"]}
    assert findings_by_id["terraform_modules_detected"]["severity"] == "info"
    assert findings_by_id["terraform_modules_detected"]["evidence"] == ["main.tf"]


def test_terraform_analysis_missing_backend_produces_medium_finding(tmp_path) -> None:
    _write_text(
        tmp_path / "main.tf",
        """
        provider "aws" {}
        variable "region" {}
        output "bucket_name" {
          value = "example"
        }
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/terraform")

    assert response.status_code == 200
    findings_by_id = {finding["id"]: finding for finding in response.json()["findings"]}
    assert findings_by_id["terraform_backend_missing"]["severity"] == "medium"
    assert findings_by_id["terraform_backend_missing"]["evidence"] == ["main.tf"]


def test_terraform_analysis_requires_scan_first(tmp_path) -> None:
    _write_text(tmp_path / "main.tf", 'provider "aws" {}')
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/analysis/terraform")

    assert response.status_code == 400
    assert response.json()["detail"] == "Project scan required before analysis"


def test_terraform_analysis_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/analysis/terraform")

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
