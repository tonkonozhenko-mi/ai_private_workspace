from app.core.domain.report import SavedWorkspaceReport, update_saved_workspace_report


class InMemoryReportRepository:
    def __init__(self) -> None:
        self._reports: dict[str, SavedWorkspaceReport] = {}

    def add_report(self, report: SavedWorkspaceReport) -> SavedWorkspaceReport:
        self._reports[report.id] = report
        return report

    def get_report(self, workspace_id: str, report_id: str) -> SavedWorkspaceReport | None:
        report = self._reports.get(report_id)
        if report is None or report.workspace_id != workspace_id:
            return None
        return report

    def list_reports(
        self,
        workspace_id: str,
        limit: int = 30,
        *,
        search: str | None = None,
        report_type: str | None = None,
        pinned_only: bool = False,
    ) -> list[SavedWorkspaceReport]:
        normalized_search = (search or "").strip().lower()
        normalized_type = (report_type or "").strip().lower()
        reports = [report for report in self._reports.values() if report.workspace_id == workspace_id]
        if normalized_type:
            reports = [report for report in reports if report.report_type == normalized_type]
        if pinned_only:
            reports = [report for report in reports if report.pinned_at]
        if normalized_search:
            reports = [
                report for report in reports
                if normalized_search in report.title.lower()
                or normalized_search in report.summary.lower()
                or normalized_search in report.export_markdown.lower()
            ]
        reports.sort(key=lambda report: (report.pinned_at is not None, report.updated_at), reverse=True)
        return reports[: max(0, limit)]

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
        current = self.get_report(workspace_id, report_id)
        if current is None:
            return None
        updated = update_saved_workspace_report(
            current,
            title=title,
            summary=summary,
            export_markdown=export_markdown,
            export_text=export_text,
            report_json=report_json,
            generated_from=generated_from,
            pinned=pinned,
        )
        self._reports[report_id] = updated
        return updated

    def delete_report(self, workspace_id: str, report_id: str) -> bool:
        current = self.get_report(workspace_id, report_id)
        if current is None:
            return False
        del self._reports[report_id]
        return True
