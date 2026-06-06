from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.timeline import TimelineEvent
from app.core.domain.timeline_backfill import TimelineBackfillResult
from app.core.domain.workspace import Workspace
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


class WorkspaceTimelineBackfillNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class BackfillWorkspaceTimelineInput:
    workspace_id: str


class BackfillWorkspaceTimelineUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        command_repository: CommandRepositoryPort,
        timeline_repository: TimelineRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.index_status_repository = index_status_repository
        self.command_repository = command_repository
        self.timeline_repository = timeline_repository

    def execute(
        self,
        request: BackfillWorkspaceTimelineInput,
    ) -> TimelineBackfillResult:
        workspace_id = request.workspace_id
        workspace = self.workspace_repository.get(workspace_id)
        if workspace is None:
            raise WorkspaceTimelineBackfillNotFoundError("Workspace not found")

        now = datetime.now(UTC).isoformat()
        candidates = self._build_candidates(
            workspace=workspace,
            latest_scan=self.project_scan_repository.get_latest_scan(workspace_id),
            index_status=self.index_status_repository.get(workspace_id),
            commands=self.command_repository.list_by_workspace(workspace_id),
            fallback_timestamp=now,
        )
        existing_events = self.timeline_repository.list_by_workspace(
            workspace_id,
            limit=1_000_000,
        )
        existing_keys = {self._event_key(event) for event in existing_events}
        backfilled_events: list[TimelineEvent] = []
        skipped_existing_events_count = 0

        for event in candidates:
            event_key = self._event_key(event)
            if event_key in existing_keys:
                skipped_existing_events_count += 1
                continue

            backfilled_events.append(self.timeline_repository.add(event))
            existing_keys.add(event_key)

        return TimelineBackfillResult(
            workspace_id=workspace_id,
            backfilled_events_count=len(backfilled_events),
            skipped_existing_events_count=skipped_existing_events_count,
            events=backfilled_events,
        )

    def _build_candidates(
        self,
        workspace: Workspace,
        latest_scan: ProjectScanResult | None,
        index_status: WorkspaceIndexStatus | None,
        commands: list[CommandProposal],
        fallback_timestamp: str,
    ) -> list[TimelineEvent]:
        candidates = [
            self._event(
                workspace_id=workspace.id,
                event_type="workspace_created",
                title="Workspace created",
                summary=f"Created workspace {workspace.name}.",
                metadata={"project_path": workspace.project_path},
                created_at=workspace.created_at.isoformat(),
            )
        ]

        if latest_scan is not None:
            candidates.append(
                self._event(
                    workspace_id=workspace.id,
                    event_type="project_scanned",
                    title="Project scanned",
                    summary=(
                        f"Scanned {latest_scan.scanned_files} files and detected "
                        f"{len(latest_scan.detected_skills)} skills."
                    ),
                    metadata={
                        "total_files": str(latest_scan.total_files),
                        "detected_skills_count": str(
                            len(latest_scan.detected_skills)
                        ),
                    },
                    created_at=fallback_timestamp,
                )
            )

        if index_status is not None and index_status.status == "indexed":
            candidates.append(
                self._event(
                    workspace_id=workspace.id,
                    event_type="workspace_indexed",
                    title="Workspace indexed",
                    summary=(
                        f"Indexed {index_status.indexed_files_count} files into "
                        f"{index_status.chunks_count} chunks."
                    ),
                    metadata={
                        "chunks_count": str(index_status.chunks_count),
                        "indexed_files_count": str(
                            index_status.indexed_files_count
                        ),
                    },
                    created_at=index_status.last_indexed_at or fallback_timestamp,
                )
            )

        for command in commands:
            candidates.extend(self._command_events(command, fallback_timestamp))

        return candidates

    def _command_events(
        self,
        command: CommandProposal,
        fallback_timestamp: str,
    ) -> list[TimelineEvent]:
        events = [
            self._event(
                workspace_id=command.workspace_id,
                event_type="command_proposed",
                title="Command proposed",
                summary=f"Proposed command: {command.command}",
                metadata={
                    "command_id": command.id,
                    "risk": command.risk,
                    "policy_mode": command.policy_mode or "",
                },
                created_at=command.created_at or fallback_timestamp,
            )
        ]

        if command.approved_at is not None or command.status in {
            CommandStatus.APPROVED.value,
            CommandStatus.EXECUTED.value,
            CommandStatus.FAILED.value,
        }:
            events.append(
                self._event(
                    workspace_id=command.workspace_id,
                    event_type="command_approved",
                    title="Command approved",
                    summary=f"Approved command: {command.command}",
                    metadata={"command_id": command.id},
                    created_at=command.approved_at or fallback_timestamp,
                )
            )

        if (
            command.rejected_at is not None
            or command.status == CommandStatus.REJECTED.value
        ):
            events.append(
                self._event(
                    workspace_id=command.workspace_id,
                    event_type="command_rejected",
                    title="Command rejected",
                    summary=f"Rejected command: {command.command}",
                    metadata={"command_id": command.id},
                    created_at=command.rejected_at or fallback_timestamp,
                )
            )

        if command.executed_at is not None or command.status in {
            CommandStatus.EXECUTED.value,
            CommandStatus.FAILED.value,
        }:
            events.append(
                self._event(
                    workspace_id=command.workspace_id,
                    event_type="command_executed",
                    title="Command execution completed",
                    summary=(
                        f"Command finished with status {command.status} "
                        f"and exit code {command.exit_code}."
                    ),
                    metadata={
                        "command_id": command.id,
                        "exit_code": (
                            str(command.exit_code)
                            if command.exit_code is not None
                            else ""
                        ),
                        "status": command.status,
                    },
                    created_at=command.executed_at or fallback_timestamp,
                )
            )

        return events

    @staticmethod
    def _event(
        workspace_id: str,
        event_type: str,
        title: str,
        summary: str,
        metadata: dict[str, str],
        created_at: str,
    ) -> TimelineEvent:
        return TimelineEvent(
            id=str(uuid4()),
            workspace_id=workspace_id,
            event_type=event_type,
            title=title,
            summary=summary,
            metadata={**metadata, "backfilled": "true"},
            created_at=created_at,
        )

    @staticmethod
    def _event_key(event: TimelineEvent) -> tuple[str, str | None]:
        command_id = (
            event.metadata.get("command_id")
            if event.event_type.startswith("command_")
            else None
        )
        return event.event_type, command_id
