from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.in_memory_command_repository import InMemoryCommandRepository
from app.adapters.memory.in_memory_index_status_repository import (
    InMemoryIndexStatusRepository,
)
from app.adapters.memory.in_memory_project_scan_repository import (
    InMemoryProjectScanRepository,
)
from app.adapters.memory.in_memory_timeline_repository import InMemoryTimelineRepository
from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.timeline import TimelineEvent
from app.core.domain.workspace import Workspace
from app.core.use_cases.list_workspaces_overview import ListWorkspacesOverviewUseCase
from app.main import app


client = TestClient(app)


def test_empty_repository_returns_zero_workspaces() -> None:
    overview = _overview_use_case().execute()

    assert overview.total_workspaces == 0
    assert overview.items == []


def test_overview_route_includes_new_workspace_without_route_conflict(tmp_path) -> None:
    workspace = _create_workspace(tmp_path, "New Overview Workspace")

    response = client.get("/workspaces/overview")

    assert response.status_code == 200
    overview = response.json()
    item = _item(overview, workspace["id"])
    assert overview["total_workspaces"] >= 1
    assert item["readiness_status"] == "needs_setup"
    assert item["quick_start_status"] == "new"
    assert item["next_action_id"] == "scan_project"
    assert item["next_action_title"] == "Run project scan"
    assert item["has_scan"] is False
    assert item["detected_skills_count"] == 0
    assert item["index_status"] == "not_indexed"


def test_overview_includes_scanned_and_indexed_workspace(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Overview\n\nOverview indexed context.")
    workspace = _create_workspace(tmp_path, "Indexed Overview Workspace")
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = client.get("/workspaces/overview")

    assert response.status_code == 200
    item = _item(response.json(), workspace["id"])
    assert item["readiness_status"] == "ready"
    assert item["quick_start_status"] == "indexed"
    assert item["next_action_id"] == "ask_first_question"
    assert item["has_scan"] is True
    assert item["detected_skills_count"] == 1
    assert item["index_status"] == "indexed"


def test_overview_counts_pending_commands_and_reports_last_event(tmp_path) -> None:
    workspace = _create_workspace(tmp_path, "Command Overview Workspace")
    command_response = client.post(
        f"/workspaces/{workspace['id']}/commands",
        json={
            "command": "git status",
            "cwd": str(tmp_path),
            "reason": "Check overview pending commands",
        },
    )
    assert command_response.status_code == 201

    response = client.get("/workspaces/overview")

    assert response.status_code == 200
    item = _item(response.json(), workspace["id"])
    assert item["commands_pending_count"] == 1
    assert item["last_event_title"] == "Command proposed"
    assert item["last_event_type"] == "command_proposed"
    assert item["last_event_at"]


def test_overview_sorts_by_most_recent_event() -> None:
    workspace_repository = InMemoryWorkspaceRepository()
    timeline_repository = InMemoryTimelineRepository()
    older = _domain_workspace("older", "2026-01-01T00:00:00+00:00")
    newer = _domain_workspace("newer", "2026-02-01T00:00:00+00:00")
    workspace_repository.create(older)
    workspace_repository.create(newer)
    timeline_repository.add(
        TimelineEvent(
            id="event-newer",
            workspace_id=newer.id,
            event_type="workspace_created",
            title="Newer workspace event",
            summary="Newer workspace created.",
            metadata={},
            created_at="2026-02-01T00:00:00+00:00",
        )
    )
    timeline_repository.add(
        TimelineEvent(
            id="event-older-recent",
            workspace_id=older.id,
            event_type="project_scanned",
            title="Most recent activity",
            summary="Older workspace was active recently.",
            metadata={},
            created_at="2026-03-01T00:00:00+00:00",
        )
    )

    overview = _overview_use_case(
        workspace_repository=workspace_repository,
        timeline_repository=timeline_repository,
    ).execute()

    assert [item.workspace_id for item in overview.items] == ["older", "newer"]
    assert overview.items[0].last_event_title == "Most recent activity"


def test_overview_derives_failed_and_real_runtime_states() -> None:
    workspace_repository = InMemoryWorkspaceRepository()
    scan_repository = InMemoryProjectScanRepository()
    index_repository = InMemoryIndexStatusRepository()
    workspace = _domain_workspace("stateful", "2026-01-01T00:00:00+00:00")
    workspace_repository.create(workspace)
    scan_repository.save_latest_scan(
        workspace.id,
        ProjectScanResult(
            project_path=workspace.project_path,
            total_files=0,
            scanned_files=0,
            skipped_files=0,
            total_size_bytes=0,
            detected_skills=[],
            files=[],
        ),
    )
    index_repository.save(
        WorkspaceIndexStatus(
            workspace_id=workspace.id,
            status="failed",
            indexed_files_count=0,
            chunks_count=0,
            skipped_files_count=0,
            last_indexed_at=None,
            last_error="Index failed",
        )
    )
    use_case = ListWorkspacesOverviewUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=scan_repository,
        index_status_repository=index_repository,
        command_repository=InMemoryCommandRepository(),
        timeline_repository=InMemoryTimelineRepository(),
        configuration={"VECTOR_STORE": "qdrant", "LLM_PROVIDER": "ollama"},
    )

    failed_item = use_case.execute().items[0]
    assert failed_item.readiness_status == "degraded"
    assert failed_item.quick_start_status == "scanned"
    assert failed_item.next_action_id == "index_workspace"

    index_repository.save(
        WorkspaceIndexStatus(
            workspace_id=workspace.id,
            status="indexed",
            indexed_files_count=0,
            chunks_count=0,
            skipped_files_count=0,
            last_indexed_at="2026-03-01T00:00:00+00:00",
            last_error=None,
        )
    )
    ready_item = use_case.execute().items[0]
    assert ready_item.readiness_status == "ready"
    assert ready_item.quick_start_status == "ready"
    assert ready_item.next_action_id == "ask_first_question"


def test_overview_read_does_not_mutate_workspace_state(tmp_path) -> None:
    workspace = _create_workspace(tmp_path, "Read Only Overview Workspace")
    workspace_id = workspace["id"]
    timeline_before = client.get(f"/workspaces/{workspace_id}/timeline").json()

    assert client.get("/workspaces/overview").status_code == 200

    assert client.get(f"/workspaces/{workspace_id}/timeline").json() == timeline_before
    assert client.get(f"/workspaces/{workspace_id}/scan").status_code == 404
    assert client.get(f"/workspaces/{workspace_id}/commands").json() == []


def _overview_use_case(
    workspace_repository=None,
    timeline_repository=None,
) -> ListWorkspacesOverviewUseCase:
    return ListWorkspacesOverviewUseCase(
        workspace_repository=workspace_repository or InMemoryWorkspaceRepository(),
        project_scan_repository=InMemoryProjectScanRepository(),
        index_status_repository=InMemoryIndexStatusRepository(),
        command_repository=InMemoryCommandRepository(),
        timeline_repository=timeline_repository or InMemoryTimelineRepository(),
        configuration={"VECTOR_STORE": "memory", "LLM_PROVIDER": "fake"},
    )


def _create_workspace(project_path: Path, name: str) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": name,
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _domain_workspace(workspace_id: str, created_at: str) -> Workspace:
    return Workspace(
        id=workspace_id,
        name=workspace_id.title(),
        project_path=f"/tmp/{workspace_id}",
        assistant_mode="developer",
        privacy_mode="local_only",
        created_at=datetime.fromisoformat(created_at).astimezone(UTC),
    )


def _item(overview: dict, workspace_id: str) -> dict:
    return next(
        item for item in overview["items"] if item["workspace_id"] == workspace_id
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
