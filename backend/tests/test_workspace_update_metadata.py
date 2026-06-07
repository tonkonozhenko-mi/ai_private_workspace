from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_update_workspace_name_trims_whitespace(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"name": "  Renamed Workspace  "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Workspace"


def test_update_workspace_assistant_mode(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"assistant_mode": "documentation"},
    )

    assert response.status_code == 200
    assert response.json()["assistant_mode"] == "documentation"


def test_update_workspace_privacy_mode(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"privacy_mode": "local_only"},
    )

    assert response.status_code == 200
    assert response.json()["privacy_mode"] == "local_only"


def test_update_multiple_fields_preserves_workspace_identity(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.patch(
        f"/workspaces/{workspace['id']}",
        json={
            "name": "Updated Workspace",
            "assistant_mode": "manager_summary",
            "privacy_mode": "local_only",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == workspace["id"]
    assert updated["name"] == "Updated Workspace"
    assert updated["assistant_mode"] == "manager_summary"
    assert updated["privacy_mode"] == "local_only"
    assert updated["project_path"] == workspace["project_path"]
    assert updated["created_at"] == workspace["created_at"]
    assert updated["archived_at"] == workspace["archived_at"]


def test_update_rejects_empty_name_and_unknown_modes(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    empty_name = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"name": "   "},
    )
    unknown_assistant = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"assistant_mode": "unknown-profile"},
    )
    unknown_privacy = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"privacy_mode": "cloud_public"},
    )

    assert empty_name.status_code == 400
    assert empty_name.json()["detail"] == "Workspace name cannot be empty"
    assert unknown_assistant.status_code == 400
    assert unknown_assistant.json()["detail"] == (
        "Unknown assistant profile: unknown-profile"
    )
    assert unknown_privacy.status_code == 400
    assert unknown_privacy.json()["detail"] == (
        "Unsupported privacy mode: cloud_public"
    )


def test_update_creates_timeline_event_with_changed_fields(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.patch(
        f"/workspaces/{workspace['id']}",
        json={
            "name": "Timeline Metadata Workspace",
            "assistant_mode": "documentation",
        },
    )

    assert response.status_code == 200
    event = _timeline(workspace["id"])[0]
    assert event["event_type"] == "workspace_metadata_updated"
    assert event["title"] == "Workspace metadata updated"
    assert event["metadata"]["updated_fields"] == "name,assistant_mode"


def test_archived_workspace_can_be_renamed_without_restoring_it(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    archive_response = client.post(f"/workspaces/{workspace['id']}/archive")
    assert archive_response.status_code == 200
    archived_at = archive_response.json()["archived_at"]

    response = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"name": "Archived But Renamed"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Archived But Renamed"
    assert response.json()["archived_at"] == archived_at


def test_update_does_not_mutate_scan_index_or_command_data(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Metadata\n\nMetadata retention context.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    command_response = client.post(
        f"/workspaces/{workspace['id']}/commands",
        json={
            "command": "git status",
            "cwd": str(tmp_path),
            "reason": "Verify metadata retention",
        },
    )
    assert command_response.status_code == 201

    response = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"name": "Metadata Retained"},
    )

    assert response.status_code == 200
    assert client.get(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.get(f"/workspaces/{workspace['id']}/index/status").json()["status"] == (
        "indexed"
    )
    commands = client.get(f"/workspaces/{workspace['id']}/commands").json()
    assert [command["id"] for command in commands] == [command_response.json()["id"]]


def test_noop_update_does_not_create_timeline_event(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    timeline_before = _timeline(workspace["id"])

    response = client.patch(f"/workspaces/{workspace['id']}", json={})

    assert response.status_code == 200
    assert _timeline(workspace["id"]) == timeline_before


def test_update_unknown_workspace_returns_404() -> None:
    response = client.patch(
        "/workspaces/missing-workspace",
        json={"name": "Missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Metadata Workspace",
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "private",
        },
    )
    assert response.status_code == 201
    return response.json()


def _timeline(workspace_id: str) -> list[dict]:
    response = client.get(f"/workspaces/{workspace_id}/timeline")
    assert response.status_code == 200
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
