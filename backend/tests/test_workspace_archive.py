from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_archive_workspace_sets_archived_at_and_is_idempotent(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    first_response = client.post(f"/workspaces/{workspace['id']}/archive")
    second_response = client.post(f"/workspaces/{workspace['id']}/archive")

    assert first_response.status_code == 200
    assert first_response.json()["archived_at"]
    assert second_response.status_code == 200
    assert second_response.json()["archived_at"] == first_response.json()["archived_at"]
    archive_events = [
        event for event in _timeline(workspace["id"]) if event["event_type"] == "workspace_archived"
    ]
    assert len(archive_events) == 1
    assert archive_events[0]["title"] == "Workspace archived"


def test_restore_workspace_clears_archived_at_and_records_event(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/archive").status_code == 200

    response = client.post(f"/workspaces/{workspace['id']}/restore")

    assert response.status_code == 200
    assert response.json()["archived_at"] is None
    events = _timeline(workspace["id"])
    assert events[0]["event_type"] == "workspace_restored"
    assert events[0]["title"] == "Workspace restored"


def test_archived_workspace_is_hidden_from_default_overview(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/archive").status_code == 200

    default_overview = client.get("/workspaces/overview")
    full_overview = client.get("/workspaces/overview?include_archived=true")

    assert default_overview.status_code == 200
    assert workspace["id"] not in _overview_ids(default_overview.json())
    assert full_overview.status_code == 200
    archived_item = next(
        item for item in full_overview.json()["items"] if item["workspace_id"] == workspace["id"]
    )
    assert archived_item["is_archived"] is True
    assert archived_item["archived_at"]
    assert archived_item["last_event_type"] == "workspace_archived"


def test_restore_returns_workspace_to_default_overview(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/archive").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/restore").status_code == 200

    overview = client.get("/workspaces/overview")

    assert overview.status_code == 200
    assert workspace["id"] in _overview_ids(overview.json())


def test_archive_does_not_delete_related_workspace_data(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Archive\n\nArchive retention context.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    command_response = client.post(
        f"/workspaces/{workspace['id']}/commands",
        json={
            "command": "git status",
            "cwd": str(tmp_path),
            "reason": "Verify archive retention",
        },
    )
    assert command_response.status_code == 201

    assert client.post(f"/workspaces/{workspace['id']}/archive").status_code == 200

    assert client.get(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.get(f"/workspaces/{workspace['id']}/index/status").json()["status"] == ("indexed")
    commands = client.get(f"/workspaces/{workspace['id']}/commands").json()
    assert [command["id"] for command in commands] == [command_response.json()["id"]]


def test_archive_and_restore_unknown_workspace_return_404() -> None:
    archive_response = client.post("/workspaces/missing-workspace/archive")
    restore_response = client.post("/workspaces/missing-workspace/restore")

    assert archive_response.status_code == 404
    assert archive_response.json()["detail"] == "Workspace not found"
    assert restore_response.status_code == 404
    assert restore_response.json()["detail"] == "Workspace not found"


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Archive Workspace",
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _timeline(workspace_id: str) -> list[dict]:
    response = client.get(f"/workspaces/{workspace_id}/timeline")
    assert response.status_code == 200
    return response.json()


def _overview_ids(overview: dict) -> set[str]:
    return {item["workspace_id"] for item in overview["items"]}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
