from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_timeline_repository import SQLiteTimelineRepository
from app.core.domain.timeline import TimelineEvent
from app.main import app

client = TestClient(app)


def test_workspace_activity_creates_newest_first_timeline_and_summary_events(
    tmp_path,
) -> None:
    _write_text(tmp_path / "README.md", "# Timeline\n\nTimeline context token.")
    workspace = _create_workspace(tmp_path)

    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200
    report_response = client.get(f"/workspaces/{workspace['id']}/reports/project-overview")
    assert report_response.status_code == 200

    command = _propose_command(workspace["id"], tmp_path)
    approve_response = client.post(f"/commands/{command['id']}/approve")
    assert approve_response.status_code == 200
    execute_response = client.post(f"/commands/{command['id']}/execute")
    assert execute_response.status_code == 200

    ask_response = client.post(
        f"/workspaces/{workspace['id']}/ask",
        json={"question": "Explain Timeline context token.", "limit": 5},
    )
    assert ask_response.status_code == 200

    timeline_response = client.get(f"/workspaces/{workspace['id']}/timeline")

    assert timeline_response.status_code == 200
    events = timeline_response.json()
    assert [event["event_type"] for event in events] == [
        "workspace_question_asked",
        "command_executed",
        "command_approved",
        "command_proposed",
        "project_overview_generated",
        "workspace_indexed",
        "project_scanned",
        "workspace_created",
    ]
    assert events[0]["metadata"]["llm_provider"] == "fake"
    assert events[1]["metadata"]["command_id"] == command["id"]
    assert events[5]["metadata"]["chunks_count"] == str(index_response.json()["chunks_count"])
    assert events[6]["metadata"]["detected_skills_count"] == str(
        len(scan_response.json()["detected_skills"])
    )

    summary_response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert summary_response.status_code == 200
    recent_events = summary_response.json()["recent_events"]
    assert len(recent_events) == 5
    assert [event["id"] for event in recent_events] == [event["id"] for event in events[:5]]


def test_workspace_timeline_limit_is_applied(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    first_command = _propose_command(workspace["id"], tmp_path)
    second_command = _propose_command(workspace["id"], tmp_path, "git diff")

    response = client.get(f"/workspaces/{workspace['id']}/timeline?limit=2")

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 2
    assert [event["metadata"]["command_id"] for event in events] == [
        second_command["id"],
        first_command["id"],
    ]


def test_timeline_events_survive_sqlite_repository_recreation(tmp_path) -> None:
    db_path = tmp_path / "workspaces.db"
    repository = SQLiteTimelineRepository(db_path)
    event = TimelineEvent(
        id="event-1",
        workspace_id="workspace-1",
        event_type="project_scanned",
        title="Project scanned",
        summary="Scanned project files.",
        metadata={"total_files": "3"},
        created_at="2026-01-01T00:00:00+00:00",
    )

    repository.add(event)
    restarted_repository = SQLiteTimelineRepository(db_path)

    assert restarted_repository.list_by_workspace("workspace-1") == [event]


def test_workspace_timeline_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/timeline")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Timeline Workspace",
            "project_path": str(project_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _propose_command(
    workspace_id: str,
    cwd: Path,
    command: str = "git status",
) -> dict:
    response = client.post(
        f"/workspaces/{workspace_id}/commands",
        json={
            "command": command,
            "cwd": str(cwd),
            "reason": "Record timeline activity",
        },
    )

    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
