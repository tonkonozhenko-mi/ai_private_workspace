from datetime import datetime

from app.core.domain.command import CommandStatus
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.workspace import Workspace
from app.core.domain.workspaces_overview import (
    WorkspaceOverviewItem,
    WorkspacesOverview,
)
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


class ListWorkspacesOverviewUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        command_repository: CommandRepositoryPort,
        timeline_repository: TimelineRepositoryPort,
        configuration: dict[str, str],
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.index_status_repository = index_status_repository
        self.command_repository = command_repository
        self.timeline_repository = timeline_repository
        self.configuration = configuration

    def execute(self) -> WorkspacesOverview:
        items = [
            self._overview_item(workspace)
            for workspace in self.workspace_repository.list()
        ]
        items.sort(key=self._sort_timestamp, reverse=True)
        return WorkspacesOverview(total_workspaces=len(items), items=items)

    def _overview_item(self, workspace: Workspace) -> WorkspaceOverviewItem:
        scan = self.project_scan_repository.get_latest_scan(workspace.id)
        index_status = self.index_status_repository.get(workspace.id)
        commands = self.command_repository.list_by_workspace(workspace.id)
        recent_events = self.timeline_repository.list_by_workspace(
            workspace.id,
            limit=1,
        )
        last_event = recent_events[0] if recent_events else None

        has_scan = scan is not None
        is_indexed = bool(
            has_scan and index_status is not None and index_status.status == "indexed"
        )
        index_failed = index_status is not None and index_status.status == "failed"
        has_real_llm = self._configured_provider_is_real("LLM_PROVIDER", "fake")
        has_persistent_vector_store = self._configured_provider_is_real(
            "VECTOR_STORE",
            "memory",
        )
        next_action_id, next_action_title = self._next_action(has_scan, is_indexed)

        return WorkspaceOverviewItem(
            workspace_id=workspace.id,
            name=workspace.name,
            project_path=workspace.project_path,
            assistant_mode=workspace.assistant_mode,
            privacy_mode=workspace.privacy_mode,
            created_at=workspace.created_at.isoformat(),
            readiness_status=self._readiness_status(
                has_scan=has_scan,
                is_indexed=is_indexed,
                index_failed=index_failed,
            ),
            quick_start_status=self._quick_start_status(
                has_scan=has_scan,
                is_indexed=is_indexed,
                has_real_llm=has_real_llm,
                has_persistent_vector_store=has_persistent_vector_store,
            ),
            next_action_id=next_action_id,
            next_action_title=next_action_title,
            has_scan=has_scan,
            detected_skills_count=len(scan.detected_skills) if scan is not None else 0,
            index_status=self._index_status(index_status),
            commands_pending_count=sum(
                command.status == CommandStatus.PENDING.value for command in commands
            ),
            last_event_title=last_event.title if last_event is not None else None,
            last_event_type=last_event.event_type if last_event is not None else None,
            last_event_at=last_event.created_at if last_event is not None else None,
        )

    def _configured_provider_is_real(self, key: str, development_value: str) -> bool:
        value = self.configuration.get(key, "").lower()
        return bool(value and value != development_value)

    @staticmethod
    def _readiness_status(
        has_scan: bool,
        is_indexed: bool,
        index_failed: bool,
    ) -> str:
        if index_failed:
            return "degraded"
        if has_scan and is_indexed:
            return "ready"
        return "needs_setup"

    @staticmethod
    def _quick_start_status(
        has_scan: bool,
        is_indexed: bool,
        has_real_llm: bool,
        has_persistent_vector_store: bool,
    ) -> str:
        if not has_scan:
            return "new"
        if not is_indexed:
            return "scanned"
        if has_real_llm and has_persistent_vector_store:
            return "ready"
        return "indexed"

    @staticmethod
    def _next_action(has_scan: bool, is_indexed: bool) -> tuple[str, str]:
        if not has_scan:
            return "scan_project", "Run project scan"
        if not is_indexed:
            return "index_workspace", "Index workspace context"
        return "ask_first_question", "Ask first workspace question"

    @staticmethod
    def _index_status(index_status: WorkspaceIndexStatus | None) -> str:
        return index_status.status if index_status is not None else "not_indexed"

    @staticmethod
    def _sort_timestamp(item: WorkspaceOverviewItem) -> datetime:
        return datetime.fromisoformat(item.last_event_at or item.created_at)
