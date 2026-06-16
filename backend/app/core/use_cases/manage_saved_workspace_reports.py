from dataclasses import dataclass

from app.core.domain.report import SavedWorkspaceReport
from app.core.ports.report_repository import ReportRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


class SavedWorkspaceReportNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class ListSavedWorkspaceReportsInput:
    workspace_id: str
    search: str | None = None
    report_type: str | None = None
    pinned_only: bool = False
    limit: int = 30


@dataclass(frozen=True)
class GetSavedWorkspaceReportInput:
    workspace_id: str
    report_id: str


@dataclass(frozen=True)
class UpdateSavedWorkspaceReportInput:
    workspace_id: str
    report_id: str
    title: str | None = None
    summary: str | None = None
    export_markdown: str | None = None
    export_text: str | None = None
    report_json: dict[str, object] | None = None
    generated_from: list[str] | None = None
    pinned: bool | None = None


@dataclass(frozen=True)
class DeleteSavedWorkspaceReportInput:
    workspace_id: str
    report_id: str


class _WorkspaceGuard:
    def __init__(self, workspace_repository: WorkspaceRepositoryPort) -> None:
        self.workspace_repository = workspace_repository

    def ensure(self, workspace_id: str) -> None:
        if self.workspace_repository.get(workspace_id) is None:
            raise SavedWorkspaceReportNotFoundError("Workspace not found")


class ListSavedWorkspaceReportsUseCase:
    def __init__(
        self, workspace_repository: WorkspaceRepositoryPort, report_repository: ReportRepositoryPort
    ) -> None:
        self.guard = _WorkspaceGuard(workspace_repository)
        self.report_repository = report_repository

    def execute(self, request: ListSavedWorkspaceReportsInput) -> list[SavedWorkspaceReport]:
        self.guard.ensure(request.workspace_id)
        return self.report_repository.list_reports(
            request.workspace_id,
            limit=request.limit,
            search=request.search,
            report_type=request.report_type,
            pinned_only=request.pinned_only,
        )


class GetSavedWorkspaceReportUseCase:
    def __init__(
        self, workspace_repository: WorkspaceRepositoryPort, report_repository: ReportRepositoryPort
    ) -> None:
        self.guard = _WorkspaceGuard(workspace_repository)
        self.report_repository = report_repository

    def execute(self, request: GetSavedWorkspaceReportInput) -> SavedWorkspaceReport:
        self.guard.ensure(request.workspace_id)
        report = self.report_repository.get_report(request.workspace_id, request.report_id)
        if report is None:
            raise SavedWorkspaceReportNotFoundError("Saved report not found")
        return report


class UpdateSavedWorkspaceReportUseCase:
    def __init__(
        self, workspace_repository: WorkspaceRepositoryPort, report_repository: ReportRepositoryPort
    ) -> None:
        self.guard = _WorkspaceGuard(workspace_repository)
        self.report_repository = report_repository

    def execute(self, request: UpdateSavedWorkspaceReportInput) -> SavedWorkspaceReport:
        self.guard.ensure(request.workspace_id)
        report = self.report_repository.update_report(
            request.workspace_id,
            request.report_id,
            title=request.title,
            summary=request.summary,
            export_markdown=request.export_markdown,
            export_text=request.export_text,
            report_json=request.report_json,
            generated_from=request.generated_from,
            pinned=request.pinned,
        )
        if report is None:
            raise SavedWorkspaceReportNotFoundError("Saved report not found")
        return report


class DeleteSavedWorkspaceReportUseCase:
    def __init__(
        self, workspace_repository: WorkspaceRepositoryPort, report_repository: ReportRepositoryPort
    ) -> None:
        self.guard = _WorkspaceGuard(workspace_repository)
        self.report_repository = report_repository

    def execute(self, request: DeleteSavedWorkspaceReportInput) -> None:
        self.guard.ensure(request.workspace_id)
        if not self.report_repository.delete_report(request.workspace_id, request.report_id):
            raise SavedWorkspaceReportNotFoundError("Saved report not found")
