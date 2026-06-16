from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import (
    command_repository,
    index_status_repository,
    project_scan_repository,
    workspace_repository,
)
from app.core.domain.command import CommandProposal
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.domain.skill import SkillMatch
from app.core.domain.workspace import Workspace
from app.main import app

client = TestClient(app)


def test_backfill_reconstructs_existing_workspace_activity_without_duplicates(
    tmp_path,
) -> None:
    workspace_id = str(uuid4())
    workspace_created_at = datetime(2025, 1, 1, tzinfo=UTC)
    workspace_repository.create(
        Workspace(
            id=workspace_id,
            name="Existing Workspace",
            project_path=str(tmp_path),
            assistant_mode="local",
            privacy_mode="private",
            created_at=workspace_created_at,
        )
    )
    project_scan_repository.save_latest_scan(
        workspace_id,
        ProjectScanResult(
            project_path=str(tmp_path),
            total_files=1,
            scanned_files=1,
            skipped_files=0,
            total_size_bytes=10,
            detected_skills=[
                SkillMatch(
                    name="Terraform",
                    category="devops",
                    confidence="high",
                    evidence=["main.tf"],
                )
            ],
            files=[
                ProjectFile(
                    path="main.tf",
                    extension=".tf",
                    size_bytes=10,
                    detected_type="terraform",
                )
            ],
        ),
    )
    index_status_repository.save(
        WorkspaceIndexStatus(
            workspace_id=workspace_id,
            status="indexed",
            indexed_files_count=1,
            chunks_count=2,
            skipped_files_count=0,
            last_indexed_at="2025-01-03T00:00:00+00:00",
            last_error=None,
        )
    )
    executed_command = _command(
        workspace_id=workspace_id,
        command_id=str(uuid4()),
        command="git status",
        status="executed",
        approved_at="2025-01-04T01:00:00+00:00",
        rejected_at=None,
        executed_at="2025-01-04T02:00:00+00:00",
        exit_code=0,
    )
    rejected_command = _command(
        workspace_id=workspace_id,
        command_id=str(uuid4()),
        command="git diff",
        status="rejected",
        approved_at=None,
        rejected_at="2025-01-05T01:00:00+00:00",
        executed_at=None,
        exit_code=None,
    )
    command_repository.create(executed_command)
    command_repository.create(rejected_command)

    first_response = client.post(f"/workspaces/{workspace_id}/timeline/backfill")

    assert first_response.status_code == 200
    first_result = first_response.json()
    assert first_result["backfilled_events_count"] == 8
    assert first_result["skipped_existing_events_count"] == 0
    event_types = [event["event_type"] for event in first_result["events"]]
    assert event_types == [
        "workspace_created",
        "project_scanned",
        "workspace_indexed",
        "command_proposed",
        "command_approved",
        "command_executed",
        "command_proposed",
        "command_rejected",
    ]
    assert all(event["metadata"]["backfilled"] == "true" for event in first_result["events"])
    assert first_result["events"][0]["created_at"] == workspace_created_at.isoformat()
    assert first_result["events"][2]["created_at"] == "2025-01-03T00:00:00+00:00"

    second_response = client.post(f"/workspaces/{workspace_id}/timeline/backfill")

    assert second_response.status_code == 200
    second_result = second_response.json()
    assert second_result["backfilled_events_count"] == 0
    assert second_result["skipped_existing_events_count"] == 8
    assert second_result["events"] == []

    timeline_response = client.get(f"/workspaces/{workspace_id}/timeline")

    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert len(timeline) == 8
    assert {
        event["metadata"]["command_id"] for event in timeline if "command_id" in event["metadata"]
    } == {executed_command.id, rejected_command.id}


def test_backfill_skips_existing_live_workspace_event(tmp_path) -> None:
    create_response = client.post(
        "/workspaces",
        json={
            "name": "Current Workspace",
            "project_path": str(tmp_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )
    assert create_response.status_code == 201
    workspace_id = create_response.json()["id"]

    response = client.post(f"/workspaces/{workspace_id}/timeline/backfill")

    assert response.status_code == 200
    result = response.json()
    assert result["backfilled_events_count"] == 0
    assert result["skipped_existing_events_count"] == 1
    assert result["events"] == []


def test_backfill_unknown_workspace_returns_404() -> None:
    response = client.post("/workspaces/missing-workspace/timeline/backfill")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _command(
    workspace_id: str,
    command_id: str,
    command: str,
    status: str,
    approved_at: str | None,
    rejected_at: str | None,
    executed_at: str | None,
    exit_code: int | None,
) -> CommandProposal:
    return CommandProposal(
        id=command_id,
        workspace_id=workspace_id,
        command=command,
        cwd="/tmp/project",
        reason="Existing command history",
        risk="readonly",
        status=status,
        created_at="2025-01-04T00:00:00+00:00",
        approved_at=approved_at,
        rejected_at=rejected_at,
        executed_at=executed_at,
        stdout="" if executed_at is not None else None,
        stderr="" if executed_at is not None else None,
        exit_code=exit_code,
        policy_allowed=True,
        policy_mode="auto_executable",
        policy_reason="Command is read-only and allowed by policy.",
    )
