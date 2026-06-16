from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_workspace_defaults_to_saved(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert workspace["persistence"] == "saved"
    assert _overview_item(workspace["id"])["persistence"] == "saved"


def test_workspace_can_be_created_temporary(tmp_path) -> None:
    workspace = _create_workspace(tmp_path, persistence="temporary")
    assert workspace["persistence"] == "temporary"
    assert _overview_item(workspace["id"])["persistence"] == "temporary"


def test_invalid_persistence_falls_back_to_saved(tmp_path) -> None:
    workspace = _create_workspace(tmp_path, persistence="nonsense")
    assert workspace["persistence"] == "saved"


def test_keep_forever_promotes_temporary_to_saved(tmp_path) -> None:
    workspace = _create_workspace(tmp_path, persistence="temporary")

    response = client.post(
        f"/workspaces/{workspace['id']}/persistence",
        json={"persistence": "saved"},
    )

    assert response.status_code == 200
    assert response.json()["persistence"] == "saved"
    assert _overview_item(workspace["id"])["persistence"] == "saved"
    events = [event["event_type"] for event in _timeline(workspace["id"])]
    assert "workspace_kept" in events


def test_set_persistence_rejects_invalid_value(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    response = client.post(
        f"/workspaces/{workspace['id']}/persistence",
        json={"persistence": "nope"},
    )
    assert response.status_code == 400


def test_set_persistence_unknown_workspace_returns_404() -> None:
    response = client.post(
        "/workspaces/missing-workspace/persistence",
        json={"persistence": "saved"},
    )
    assert response.status_code == 404


def test_purge_temporary_deletes_only_temporary_workspaces(tmp_path) -> None:
    saved = _create_workspace(tmp_path / "saved", persistence="saved")
    temp_one = _create_workspace(tmp_path / "temp1", persistence="temporary")
    temp_two = _create_workspace(tmp_path / "temp2", persistence="temporary")

    response = client.post("/workspaces/temporary/purge")

    assert response.status_code == 200
    body = response.json()
    assert body["deleted_count"] >= 2
    assert temp_one["id"] in body["deleted_ids"]
    assert temp_two["id"] in body["deleted_ids"]
    assert saved["id"] not in body["deleted_ids"]

    assert client.get(f"/workspaces/{saved['id']}").status_code == 200
    assert client.get(f"/workspaces/{temp_one['id']}").status_code == 404
    assert client.get(f"/workspaces/{temp_two['id']}").status_code == 404


def _create_workspace(project_path: Path, persistence: str | None = None) -> dict:
    project_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": "Persistence Workspace",
        "project_path": str(project_path),
        "assistant_mode": "developer",
        "privacy_mode": "local_only",
    }
    if persistence is not None:
        payload["persistence"] = persistence
    response = client.post("/workspaces", json=payload)
    assert response.status_code == 201
    return response.json()


def _overview_item(workspace_id: str) -> dict:
    overview = client.get("/workspaces/overview?include_archived=true")
    assert overview.status_code == 200
    return next(item for item in overview.json()["items"] if item["workspace_id"] == workspace_id)


def _timeline(workspace_id: str) -> list[dict]:
    response = client.get(f"/workspaces/{workspace_id}/timeline")
    assert response.status_code == 200
    return response.json()
