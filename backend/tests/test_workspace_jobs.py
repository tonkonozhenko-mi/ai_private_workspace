from pathlib import Path
import time

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_scan_workspace_job_completes_and_updates_latest_scan(tmp_path: Path) -> None:
    _write_text(tmp_path / "src" / "app.py", "print('hello')")
    workspace = _create_workspace(tmp_path)

    start_response = client.post(f"/workspaces/{workspace['id']}/jobs/scan")

    assert start_response.status_code == 200
    job = _wait_for_job(workspace["id"], start_response.json()["job_id"])
    assert job["status"] == "completed"
    assert job["job_type"] == "scan"
    assert job["result_summary"]["scanned_files"] == "1"

    latest_scan_response = client.get(f"/workspaces/{workspace['id']}/scan")
    assert latest_scan_response.status_code == 200
    assert latest_scan_response.json()["scanned_files"] == 1


def test_workspace_job_cancel_unknown_returns_404(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.post(f"/workspaces/{workspace['id']}/jobs/missing/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace job not found"


def _wait_for_job(workspace_id: str, job_id: str) -> dict:
    for _ in range(50):
        response = client.get(f"/workspaces/{workspace_id}/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.05)
    raise AssertionError("Job did not finish")


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Job Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
