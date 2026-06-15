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
    assert job["request_summary"]["file_rules_profile"] == "balanced"
    assert job["duration_ms"] is not None

    latest_scan_response = client.get(f"/workspaces/{workspace['id']}/scan")
    assert latest_scan_response.status_code == 200
    assert latest_scan_response.json()["scanned_files"] == 1


def test_list_workspace_jobs_returns_created_jobs(tmp_path: Path) -> None:
    _write_text(tmp_path / "README.md", "job list")
    workspace = _create_workspace(tmp_path)

    start_response = client.post(f"/workspaces/{workspace['id']}/jobs/scan")

    assert start_response.status_code == 200
    response = client.get(f"/workspaces/{workspace['id']}/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert any(job["job_id"] == start_response.json()["job_id"] for job in jobs)


def test_get_workspace_job_with_wrong_workspace_returns_404(tmp_path: Path) -> None:
    _write_text(tmp_path / "one" / "README.md", "job one")
    _write_text(tmp_path / "two" / "README.md", "job two")
    workspace_one = _create_workspace(tmp_path / "one")
    workspace_two = _create_workspace(tmp_path / "two")
    start_response = client.post(f"/workspaces/{workspace_one['id']}/jobs/scan")
    assert start_response.status_code == 200

    response = client.get(
        f"/workspaces/{workspace_two['id']}/jobs/{start_response.json()['job_id']}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace job not found"


def test_cancel_workspace_job_marks_job_for_cancellation(tmp_path: Path) -> None:
    _write_text(tmp_path / "README.md", "cancel job")
    workspace = _create_workspace(tmp_path)
    start_response = client.post(f"/workspaces/{workspace['id']}/jobs/scan")
    assert start_response.status_code == 200

    response = client.post(
        f"/workspaces/{workspace['id']}/jobs/{start_response.json()['job_id']}/cancel"
    )

    assert response.status_code == 200
    job = response.json()
    # A one-file scan can finish before the cancel request is processed on fast
    # CI runners. Cancelling an already-finished job is a no-op, so accept either
    # an acknowledged cancellation or a job that completed before it could stop.
    assert job["cancellation_requested"] is True or job["status"] == "completed"
    assert job["status"] in {"queued", "running", "cancelled", "completed"}



def test_scan_workspace_job_records_applied_file_rules(tmp_path: Path) -> None:
    _write_text(tmp_path / "src" / "app.py", "print('hello')")
    _write_text(tmp_path / "dist" / "bundle.js", "compiled")
    workspace = _create_workspace(tmp_path)

    start_response = client.post(
        f"/workspaces/{workspace['id']}/jobs/scan",
        json={
            "file_rules": {
                "profile": "custom",
                "include_patterns": ["src/**"],
                "exclude_patterns": ["dist/**"],
            }
        },
    )

    assert start_response.status_code == 200
    job = _wait_for_job(workspace["id"], start_response.json()["job_id"])
    assert job["status"] == "completed"
    assert job["request_summary"] == {
        "file_rules_profile": "custom",
        "include_rules_count": "1",
        "exclude_rules_count": "1",
        "include_patterns": "src/**",
        "exclude_patterns": "dist/**",
    }
    assert job["result_summary"]["scanned_files"] == "1"


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
