from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_scan_project_detects_expected_skills_and_files(tmp_path) -> None:
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
    _write_text(tmp_path / "node_modules" / "ignored.py", "print('ignored')")
    _write_bytes(tmp_path / "large.bin", b"x" * (2 * 1024 * 1024 + 1))

    response = client.post("/projects/scan", json={"project_path": str(tmp_path)})

    assert response.status_code == 200
    result = response.json()
    detected_skill_names = {skill["name"] for skill in result["detected_skills"]}
    skills_by_name = {skill["name"]: skill for skill in result["detected_skills"]}
    file_paths = {project_file["path"] for project_file in result["files"]}

    assert {
        "Terraform",
        "Python",
        "Docker",
        "GitLab CI",
        "Documentation",
        "Helm",
        "Kubernetes",
    }.issubset(detected_skill_names)
    assert "node_modules/ignored.py" not in file_paths
    assert "large.bin" not in file_paths
    assert result["skipped_files"] == 1
    assert skills_by_name["Terraform"]["category"] == "devops"
    assert skills_by_name["Python"]["category"] == "developer"
    assert skills_by_name["Documentation"]["category"] == "documentation"
    assert skills_by_name["YAML/Configuration"]["category"] == "general"


def test_scan_project_invalid_path_returns_api_error(tmp_path) -> None:
    response = client.post(
        "/projects/scan",
        json={"project_path": str(tmp_path / "missing-project")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Project path does not exist"


def test_scan_project_file_path_returns_api_error(tmp_path) -> None:
    project_file = tmp_path / "not-a-directory.txt"
    _write_text(project_file, "not a directory")

    response = client.post("/projects/scan", json={"project_path": str(project_file)})

    assert response.status_code == 400
    assert response.json()["detail"] == "Project path is not a directory"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
