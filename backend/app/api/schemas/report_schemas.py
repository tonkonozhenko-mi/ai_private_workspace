from pydantic import BaseModel

from app.core.domain.report import ProjectOverviewReport, ReportCatalog, ReportSection, ReportTemplate


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
    report_type: str = "project_overview"
    export_markdown: str = ""
    safety_note: str = ""


class ReportTemplateResponse(BaseModel):
    id: str
    title: str
    description: str
    best_for: str
    requires_scan: bool
    output_style: str
    source_strategy: str


class ReportCatalogResponse(BaseModel):
    workspace_id: str
    templates: list[ReportTemplateResponse]
    safety_notes: list[str]


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
        report_type=report.report_type,
        export_markdown=report.export_markdown,
        safety_note=report.safety_note,
    )


def to_report_template_response(template: ReportTemplate) -> ReportTemplateResponse:
    return ReportTemplateResponse(
        id=template.id,
        title=template.title,
        description=template.description,
        best_for=template.best_for,
        requires_scan=template.requires_scan,
        output_style=template.output_style,
        source_strategy=template.source_strategy,
    )


def to_report_catalog_response(catalog: ReportCatalog) -> ReportCatalogResponse:
    return ReportCatalogResponse(
        workspace_id=catalog.workspace_id,
        templates=[to_report_template_response(template) for template in catalog.templates],
        safety_notes=catalog.safety_notes,
    )
