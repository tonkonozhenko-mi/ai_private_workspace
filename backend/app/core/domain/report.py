from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass(frozen=True)
class SavedWorkspaceReport:
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

    @property
    def is_pinned(self) -> bool:
        return self.pinned_at is not None


def create_saved_workspace_report(report: ProjectOverviewReport) -> SavedWorkspaceReport:
    now = utc_now_iso()
    return SavedWorkspaceReport(
        id=str(uuid4()),
        workspace_id=report.workspace_id,
        report_type=report.report_type,
        title=report.title.strip()[:180] or "Workspace report",
        summary=report.summary.strip(),
        export_markdown=report.export_markdown,
        export_text=render_report_text(report),
        report_json=report_to_dict(report),
        generated_from=list(report.generated_from),
        created_at=now,
        updated_at=now,
        pinned_at=None,
    )


def update_saved_workspace_report(
    saved: SavedWorkspaceReport,
    *,
    title: str | None = None,
    summary: str | None = None,
    pinned: bool | None = None,
) -> SavedWorkspaceReport:
    pinned_at = saved.pinned_at
    if pinned is True and pinned_at is None:
        pinned_at = utc_now_iso()
    elif pinned is False:
        pinned_at = None
    return SavedWorkspaceReport(
        id=saved.id,
        workspace_id=saved.workspace_id,
        report_type=saved.report_type,
        title=(title if title is not None else saved.title).strip()[:180] or "Workspace report",
        summary=(summary if summary is not None else saved.summary).strip(),
        export_markdown=saved.export_markdown,
        export_text=saved.export_text,
        report_json=dict(saved.report_json),
        generated_from=list(saved.generated_from),
        created_at=saved.created_at,
        updated_at=utc_now_iso(),
        pinned_at=pinned_at,
    )


def report_to_dict(report: ProjectOverviewReport) -> dict[str, object]:
    return {
        "workspace_id": report.workspace_id,
        "title": report.title,
        "summary": report.summary,
        "sections": [
            {"title": section.title, "content": section.content, "bullets": list(section.bullets)}
            for section in report.sections
        ],
        "generated_from": list(report.generated_from),
        "report_type": report.report_type,
        "export_markdown": report.export_markdown,
        "safety_note": report.safety_note,
    }


def render_report_text(report: ProjectOverviewReport) -> str:
    lines = [report.title, "", report.summary, "", f"Safety: {report.safety_note}", ""]
    for section in report.sections:
        lines.extend([section.title, "", section.content, ""])
        for bullet in section.bullets:
            lines.append(f"- {bullet}")
        lines.append("")
    lines.extend(["Generated from", ""])
    for source in report.generated_from:
        lines.append(f"- {source}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_report_markdown(report: ProjectOverviewReport) -> str:
    lines = [f"# {report.title}", "", report.summary, "", f"> Safety: {report.safety_note}", ""]
    for section in report.sections:
        lines.extend([f"## {section.title}", "", section.content, ""])
        for bullet in section.bullets:
            lines.append(f"- {bullet}")
        lines.append("")
    lines.extend(["## Generated from", ""])
    for source in report.generated_from:
        lines.append(f"- {source}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"
