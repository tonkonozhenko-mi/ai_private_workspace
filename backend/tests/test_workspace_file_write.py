from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "File Write Workspace",
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_explicit_file_write_creates_file_inside_workspace(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.post(
        f"/workspaces/{workspace['id']}/files/write",
        json={
            "relative_path": "docs/generated.md",
            "content": "# Generated\n\nReviewed content.",
            "overwrite": False,
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "created"
    assert (tmp_path / "docs/generated.md").read_text() == ("# Generated\n\nReviewed content.")


def test_file_write_requires_explicit_overwrite(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    target = tmp_path / "README.md"
    target.write_text("Original")

    blocked = client.post(
        f"/workspaces/{workspace['id']}/files/write",
        json={
            "relative_path": "README.md",
            "content": "Replacement",
            "overwrite": False,
        },
    )
    replaced = client.post(
        f"/workspaces/{workspace['id']}/files/write",
        json={
            "relative_path": "README.md",
            "content": "Replacement",
            "overwrite": True,
        },
    )

    assert blocked.status_code == 400
    assert target.read_text() == "Replacement"
    assert replaced.status_code == 201
    assert replaced.json()["status"] == "replaced"


def test_file_write_blocks_paths_outside_workspace(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.post(
        f"/workspaces/{workspace['id']}/files/write",
        json={
            "relative_path": "../outside.md",
            "content": "Blocked",
            "overwrite": False,
        },
    )

    assert response.status_code == 400
    assert "relative path inside the workspace" in response.json()["detail"]


def test_file_write_does_not_recreate_missing_workspace_directory(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    workspace = _create_workspace(project_path)
    project_path.rmdir()

    response = client.post(
        f"/workspaces/{workspace['id']}/files/write",
        json={
            "relative_path": "notes/generated.md",
            "content": "Do not recreate the missing workspace.",
            "overwrite": False,
        },
    )

    assert response.status_code == 400
    assert not project_path.exists()


def test_file_write_creates_timeline_event(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.post(
        f"/workspaces/{workspace['id']}/files/write",
        json={
            "relative_path": "notes/assistant.txt",
            "content": "Reviewed answer",
            "overwrite": False,
        },
    )
    timeline = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    assert response.status_code == 201
    assert timeline[0]["event_type"] == "workspace_file_written"
    assert timeline[0]["metadata"]["relative_path"] == "notes/assistant.txt"
