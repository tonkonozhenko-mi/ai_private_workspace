from typing import Protocol

from app.core.domain.report import SavedWorkspaceReport


class ReportRepositoryPort(Protocol):
    def add_report(self, report: SavedWorkspaceReport) -> SavedWorkspaceReport:
        """Persist a generated workspace report."""

    def get_report(self, workspace_id: str, report_id: str) -> SavedWorkspaceReport | None:
        """Return one saved report."""

    def list_reports(
        self,
        workspace_id: str,
        limit: int = 30,
        *,
        search: str | None = None,
        report_type: str | None = None,
        pinned_only: bool = False,
    ) -> list[SavedWorkspaceReport]:
        """Return saved reports for a workspace."""

    def update_report(
        self,
        workspace_id: str,
        report_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        export_markdown: str | None = None,
        export_text: str | None = None,
        report_json: dict[str, object] | None = None,
        generated_from: list[str] | None = None,
        pinned: bool | None = None,
    ) -> SavedWorkspaceReport | None:
        """Update report metadata or edited content."""

    def delete_report(self, workspace_id: str, report_id: str) -> bool:
        """Delete a saved report."""
