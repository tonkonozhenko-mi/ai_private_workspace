from pydantic import BaseModel

from app.core.domain.report import ProjectOverviewReport, ReportSection


class ReportSectionResponse(BaseModel):
    title: str
    content: str
    bullets: list[str]


class ProjectOverviewReportResponse(BaseModel):
    workspace_id: str
    title: str
    summary: str
    sections: list[ReportSectionResponse]
    generated_from: list[str]


def to_report_section_response(section: ReportSection) -> ReportSectionResponse:
    return ReportSectionResponse(
        title=section.title,
        content=section.content,
        bullets=section.bullets,
    )


def to_project_overview_report_response(
    report: ProjectOverviewReport,
) -> ProjectOverviewReportResponse:
    return ProjectOverviewReportResponse(
        workspace_id=report.workspace_id,
        title=report.title,
        summary=report.summary,
        sections=[
            to_report_section_response(section) for section in report.sections
        ],
        generated_from=report.generated_from,
    )
