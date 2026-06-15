from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_overview_exposes_storage_fields(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    item = _overview_item(workspace["id"])

    assert "storage_total_bytes" in item
    assert "storage_breakdown" in item
    assert isinstance(item["storage_total_bytes"], int)
    assert set(item["storage_breakdown"]) >= {
        "index",
        "conversations",
        "notes",
        "scan",
        "other",
    }


def test_storage_grows_after_scan_and_index(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Storage\n\n" + ("context line\n" * 50))
    workspace = _create_workspace(tmp_path)
    baseline = _storage(workspace["id"])["total_bytes"]

    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    after = _storage(workspace["id"], recompute=True)
    assert after["total_bytes"] > baseline
    assert after["breakdown"]["scan"] > 0


def test_clear_index_resets_status_and_keeps_workspace(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Clear\n\nindexable content here.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    assert (
        client.get(f"/workspaces/{workspace['id']}/index/status").json()["status"]
        == "indexed"
    )

    response = client.post(f"/workspaces/{workspace['id']}/index/clear")

    assert response.status_code == 200
    assert response.json()["breakdown"]["index"] == 0
    assert (
        client.get(f"/workspaces/{workspace['id']}/index/status").json()["status"]
        == "not_indexed"
    )
    # Workspace itself is untouched.
    assert client.get(f"/workspaces/{workspace['id']}").status_code == 200
    events = [
        event["event_type"]
        for event in _timeline(workspace["id"])
    ]
    assert "workspace_index_cleared" in events


def test_delete_workspace_removes_it_everywhere(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Delete\n\nindexable content here.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = client.request("DELETE", f"/workspaces/{workspace['id']}")

    assert response.status_code == 204
    assert client.get(f"/workspaces/{workspace['id']}").status_code == 404
    assert workspace["id"] not in _overview_ids(
        client.get("/workspaces/overview?include_archived=true").json()
    )
    # Scan data is gone too.
    assert client.get(f"/workspaces/{workspace['id']}/scan").status_code == 404


def test_delete_only_targets_requested_workspace(tmp_path) -> None:
    keep = _create_workspace(tmp_path / "keep")
    drop = _create_workspace(tmp_path / "drop")

    assert client.request("DELETE", f"/workspaces/{drop['id']}").status_code == 204

    assert client.get(f"/workspaces/{keep['id']}").status_code == 200
    assert client.get(f"/workspaces/{drop['id']}").status_code == 404


def test_delete_and_clear_unknown_workspace_return_404() -> None:
    delete_response = client.request("DELETE", "/workspaces/missing-workspace")
    clear_response = client.post("/workspaces/missing-workspace/index/clear")
    storage_response = client.get("/workspaces/missing-workspace/storage")

    assert delete_response.status_code == 404
    assert clear_response.status_code == 404
    assert storage_response.status_code == 404


def _create_workspace(project_path: Path) -> dict:
    project_path.mkdir(parents=True, exist_ok=True)
    response = client.post(
        "/workspaces",
        json={
            "name": "Storage Workspace",
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _overview_item(workspace_id: str) -> dict:
    overview = client.get("/workspaces/overview?include_archived=true")
    assert overview.status_code == 200
    return next(
        item
        for item in overview.json()["items"]
        if item["workspace_id"] == workspace_id
    )


def _storage(workspace_id: str, recompute: bool = False) -> dict:
    response = client.get(
        f"/workspaces/{workspace_id}/storage",
        params={"recompute": str(recompute).lower()},
    )
    assert response.status_code == 200
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
