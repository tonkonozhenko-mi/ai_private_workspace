from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReportSection:
    title: str
    content: str
    bullets: list[str]


@dataclass(frozen=True)
class ProjectOverviewReport:
    workspace_id: str
    title: str
    summary: str
    sections: list[ReportSection]
    generated_from: list[str]
    report_type: str = "project_overview"
    export_markdown: str = ""
    safety_note: str = (
        "This report is generated from local workspace data, deterministic scan results, "
        "saved notes, and captured conversation metadata. Review it before sharing."
    )


@dataclass(frozen=True)
class ReportTemplate:
    id: str
    title: str
    description: str
    best_for: str
    requires_scan: bool = True
    output_style: str = "markdown"
    source_strategy: str = "latest scan + deterministic analysis + saved workspace context"


@dataclass(frozen=True)
class ReportCatalog:
    workspace_id: str
    templates: list[ReportTemplate] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
