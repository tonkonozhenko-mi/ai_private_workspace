from pydantic import BaseModel

from app.core.domain.report import (
    ProjectOverviewReport,
    ReportCatalog,
    ReportQualityCheck,
    ReportQualitySummary,
    ReportSection,
    ReportTemplate,
    SavedWorkspaceReport,
    evaluate_report_quality,
    evaluate_saved_report_quality,
)


class ReportSectionResponse(BaseModel):
    title: str
    content: str
    bullets: list[str]


class ReportQualityCheckResponse(BaseModel):
    id: str
    label: str
    status: str
    detail: str


class ReportQualitySummaryResponse(BaseModel):
    score: int
    status: str
    source_coverage_count: int
    source_coverage_label: str
    checks: list[ReportQualityCheckResponse]
    warnings: list[str]


class ProjectOverviewReportResponse(BaseModel):
    workspace_id: str
    title: str
    summary: str
    sections: list[ReportSectionResponse]
    generated_from: list[str]
    report_type: str = "project_overview"
    export_markdown: str = ""
    safety_note: str = ""
    quality: ReportQualitySummaryResponse


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




def to_report_quality_check_response(check: ReportQualityCheck) -> ReportQualityCheckResponse:
    return ReportQualityCheckResponse(
        id=check.id,
        label=check.label,
        status=check.status,
        detail=check.detail,
    )


def to_report_quality_summary_response(quality: ReportQualitySummary) -> ReportQualitySummaryResponse:
    return ReportQualitySummaryResponse(
        score=quality.score,
        status=quality.status,
        source_coverage_count=quality.source_coverage_count,
        source_coverage_label=quality.source_coverage_label,
        checks=[to_report_quality_check_response(check) for check in quality.checks],
        warnings=list(quality.warnings),
    )

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
        quality=to_report_quality_summary_response(evaluate_report_quality(report)),
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




class BuildCustomWorkspaceReportRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    report_type: str = "custom_report"
    note_ids: list[str] = []
    conversation_ids: list[str] = []
    extra_context: str | None = None


class SaveCustomWorkspaceReportRequest(BuildCustomWorkspaceReportRequest):
    pass


class SaveEditedWorkspaceReportRequest(BaseModel):
    title: str
    summary: str = ""
    report_type: str = "edited_report"
    sections: list[ReportSectionResponse] = []
    generated_from: list[str] = []
    export_markdown: str
    safety_note: str = ""

class SavedWorkspaceReportResponse(BaseModel):
    id: str
    workspace_id: str
    report_type: str
    title: str
    summary: str
    export_markdown: str
    export_text: str
    report_json: dict[str, object]
    generated_from: list[str]
    created_at: str
    updated_at: str
    pinned_at: str | None = None
    is_pinned: bool
    quality: ReportQualitySummaryResponse


class UpdateSavedWorkspaceReportRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    export_markdown: str | None = None
    export_text: str | None = None
    report_json: dict[str, object] | None = None
    generated_from: list[str] | None = None


class SavedReportPinRequest(BaseModel):
    pinned: bool


def to_saved_workspace_report_response(report: SavedWorkspaceReport) -> SavedWorkspaceReportResponse:
    return SavedWorkspaceReportResponse(
        id=report.id,
        workspace_id=report.workspace_id,
        report_type=report.report_type,
        title=report.title,
        summary=report.summary,
        export_markdown=report.export_markdown,
        export_text=report.export_text,
        report_json=report.report_json,
        generated_from=report.generated_from,
        created_at=report.created_at,
        updated_at=report.updated_at,
        pinned_at=report.pinned_at,
        is_pinned=report.is_pinned,
        quality=to_report_quality_summary_response(evaluate_saved_report_quality(report)),
    )
