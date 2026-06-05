from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_project_scan_repository import SQLiteProjectScanRepository
from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.domain.skill import SkillMatch
from app.main import app


client = TestClient(app)


def test_scan_workspace_project_saves_and_returns_latest_scan(tmp_path) -> None:
    _write_text(tmp_path / "main.tf", 'resource "null_resource" "example" {}')
    _write_text(tmp_path / "app.py", "print('hello')")
    _write_text(tmp_path / "README.md", "# Example Project")

    workspace = _create_workspace(tmp_path)

    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")

    assert scan_response.status_code == 200
    scan_result = scan_response.json()
    skill_names = {skill["name"] for skill in scan_result["detected_skills"]}
    assert {"Terraform", "Python", "Documentation"}.issubset(skill_names)

    latest_scan_response = client.get(f"/workspaces/{workspace['id']}/scan")

    assert latest_scan_response.status_code == 200
    assert latest_scan_response.json() == scan_result


def test_workspace_scan_survives_sqlite_repository_recreation(tmp_path) -> None:
    db_path = tmp_path / "workspaces.db"
    repository = SQLiteProjectScanRepository(db_path)
    scan_result = ProjectScanResult(
        project_path="/tmp/example-project",
        total_files=1,
        scanned_files=1,
        skipped_files=0,
        total_size_bytes=10,
        detected_skills=[
            SkillMatch(
                name="Python",
                category="developer",
                confidence="high",
                evidence=["app.py"],
            )
        ],
        files=[
            ProjectFile(
                path="app.py",
                extension=".py",
                size_bytes=10,
                detected_type="python",
            )
        ],
    )

    repository.save_latest_scan("workspace-1", scan_result)
    restarted_repository = SQLiteProjectScanRepository(db_path)

    assert restarted_repository.get_latest_scan("workspace-1") == scan_result


def test_scan_unknown_workspace_returns_404() -> None:
    response = client.post("/workspaces/missing-workspace/scan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_get_missing_workspace_scan_returns_404(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/scan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace scan not found"


def test_scan_workspace_with_invalid_project_path_returns_api_error(tmp_path) -> None:
    missing_project_path = tmp_path / "missing-project"
    workspace = _create_workspace(missing_project_path)

    response = client.post(f"/workspaces/{workspace['id']}/scan")

    assert response.status_code == 400
    assert response.json()["detail"] == "Project path does not exist"


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
