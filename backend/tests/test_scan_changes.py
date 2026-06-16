import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def _bump_mtime(path: Path) -> None:
    # Push mtime forward so a same-size content change is still detectable even
    # on filesystems with coarse timestamp resolution.
    stat = path.stat()
    os.utime(path, (stat.st_atime + 5, stat.st_mtime + 5))


def test_scan_changes_reports_no_changes_right_after_scan(tmp_path) -> None:
    _write_text(tmp_path / "app.py", "print('hello')")
    _write_text(tmp_path / "README.md", "# Example Project")

    workspace = _create_workspace(tmp_path)

    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    changes_response = client.get(f"/workspaces/{workspace['id']}/scan/changes")
    assert changes_response.status_code == 200
    changes = changes_response.json()
    assert changes["has_baseline"] is True
    assert changes["changed"] is False
    assert changes["added_count"] == 0
    assert changes["removed_count"] == 0
    assert changes["modified_count"] == 0
    assert changes["current_file_count"] == changes["previous_file_count"]


def test_scan_changes_detects_added_and_modified_files(tmp_path) -> None:
    app_file = tmp_path / "app.py"
    _write_text(app_file, "print('hello')")
    _write_text(tmp_path / "README.md", "# Example Project")

    workspace = _create_workspace(tmp_path)

    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200

    # Add a new file and change the size of an existing one.
    _write_text(tmp_path / "extra.py", "print('extra module here')")
    app_file.write_text("print('hello world, now longer')", encoding="utf-8")
    _bump_mtime(app_file)

    changes_response = client.get(f"/workspaces/{workspace['id']}/scan/changes")
    assert changes_response.status_code == 200
    changes = changes_response.json()
    assert changes["has_baseline"] is True
    assert changes["changed"] is True
    assert changes["added_count"] >= 1
    assert changes["modified_count"] >= 1


def test_scan_changes_detects_removed_files(tmp_path) -> None:
    removable = tmp_path / "removable.py"
    _write_text(removable, "print('temporary')")
    _write_text(tmp_path / "app.py", "print('hello')")

    workspace = _create_workspace(tmp_path)

    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200

    removable.unlink()

    changes_response = client.get(f"/workspaces/{workspace['id']}/scan/changes")
    assert changes_response.status_code == 200
    changes = changes_response.json()
    assert changes["changed"] is True
    assert changes["removed_count"] >= 1


def test_scan_changes_without_baseline_reports_no_baseline(tmp_path) -> None:
    _write_text(tmp_path / "app.py", "print('hello')")

    workspace = _create_workspace(tmp_path)

    changes_response = client.get(f"/workspaces/{workspace['id']}/scan/changes")
    assert changes_response.status_code == 200
    changes = changes_response.json()
    assert changes["has_baseline"] is False
    assert changes["changed"] is False


def test_scan_changes_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/scan/changes")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"
