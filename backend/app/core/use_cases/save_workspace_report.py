from dataclasses import dataclass

from app.core.domain.report import SavedWorkspaceReport, create_saved_workspace_report
from app.core.ports.report_repository import ReportRepositoryPort
from app.core.use_cases.generate_workspace_report import (
    GenerateWorkspaceReportInput,
    GenerateWorkspaceReportUseCase,
)


@dataclass(frozen=True)
class SaveWorkspaceReportInput:
    workspace_id: str
    report_type: str


class SaveWorkspaceReportUseCase:
    def __init__(
        self,
        report_generator: GenerateWorkspaceReportUseCase,
        report_repository: ReportRepositoryPort,
    ) -> None:
        self.report_generator = report_generator
        self.report_repository = report_repository

    def execute(self, request: SaveWorkspaceReportInput) -> SavedWorkspaceReport:
        report = self.report_generator.execute(
            GenerateWorkspaceReportInput(
                workspace_id=request.workspace_id,
                report_type=request.report_type,
            )
        )
        saved = create_saved_workspace_report(report)
        return self.report_repository.add_report(saved)
