from dataclasses import dataclass

from app.core.domain.conversation import ConversationAnswerNote, WorkspaceConversation
from app.core.domain.report import ProjectOverviewReport, ReportCatalog, ReportSection, ReportTemplate
from app.core.ports.conversation_repository import ConversationRepositoryPort
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import AddTimelineEventInput, AddTimelineEventUseCase
from app.core.use_cases.generate_project_overview_report import (
    GenerateProjectOverviewReportInput,
    GenerateProjectOverviewReportUseCase,
    ProjectOverviewReportScanRequiredError,
    ProjectOverviewReportWorkspaceNotFoundError,
)

REPORT_TEMPLATES: tuple[ReportTemplate, ...] = (
    ReportTemplate(
        id="project_overview",
        title="Project overview",
        description="High-level summary of workspace structure, technologies, findings, and next steps.",
        best_for="First project understanding and onboarding kickoff.",
    ),
    ReportTemplate(
        id="onboarding_guide",
        title="Onboarding guide",
        description="Beginner-friendly handover document for a new engineer joining the project.",
        best_for="New team member onboarding, KT handover, and setup walkthroughs.",
    ),
    ReportTemplate(
        id="devops_review",
        title="DevOps review",
        description="Infrastructure, CI/CD, runtime, operational risk, and follow-up checklist.",
        best_for="DevOps review, platform handover, and sprint planning.",
    ),
    ReportTemplate(
        id="architecture_summary",
        title="Architecture summary",
        description="Compact architecture notes based on detected project components and source evidence.",
        best_for="Architecture discussions, README architecture section, and team alignment.",
    ),
    ReportTemplate(
        id="runbook",
        title="Runbook draft",
        description="Operational checklist with verification, troubleshooting, and safety reminders.",
        best_for="Support handover, incident preparation, and local-first operations notes.",
    ),
)


@dataclass(frozen=True)
class GetWorkspaceReportCatalogInput:
    workspace_id: str


@dataclass(frozen=True)
class GenerateWorkspaceReportInput:
    workspace_id: str
    report_type: str


class WorkspaceReportNotFoundError(ValueError):
    pass


class WorkspaceReportScanRequiredError(ValueError):
    pass


class WorkspaceReportTypeNotFoundError(ValueError):
    pass


class GetWorkspaceReportCatalogUseCase:
    def __init__(self, workspace_repository: WorkspaceRepositoryPort) -> None:
        self.workspace_repository = workspace_repository

    def execute(self, request: GetWorkspaceReportCatalogInput) -> ReportCatalog:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceReportNotFoundError("Workspace not found")
        return ReportCatalog(
            workspace_id=workspace.id,
            templates=list(REPORT_TEMPLATES),
            safety_notes=[
                "Reports are generated only after explicit user action.",
                "Reports do not execute shell commands, scan, index, rebuild, or upload data.",
                "Project claims should stay grounded in local scan results, saved notes, and captured sources.",
            ],
        )


class GenerateWorkspaceReportUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
        conversation_repository: ConversationRepositoryPort | None = None,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        self.conversation_repository = conversation_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: GenerateWorkspaceReportInput) -> ProjectOverviewReport:
        report_type = normalize_report_type(request.report_type)
        if report_type not in {template.id for template in REPORT_TEMPLATES}:
            raise WorkspaceReportTypeNotFoundError(f"Unknown report type: {request.report_type}")

        base_report = self._generate_base_report(request.workspace_id)
        notes = self._notes(request.workspace_id)
        conversations = self._conversations(request.workspace_id)

        if report_type == "project_overview":
            report = self._finalize_report(
                base_report,
                report_type=report_type,
                title=base_report.title,
                summary=base_report.summary,
                sections=base_report.sections + [self._workspace_context_section(notes, conversations)],
                generated_from=base_report.generated_from + ["saved_answer_notes", "conversation_metadata"],
            )
        else:
            report = self._build_specialized_report(
                base_report=base_report,
                report_type=report_type,
                notes=notes,
                conversations=conversations,
            )

        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="workspace_report_generated",
                    title=f"Report generated: {self._template(report_type).title}",
                    summary="Generated a local-first workspace report from saved project context.",
                    metadata={
                        "report_type": report_type,
                        "sections_count": str(len(report.sections)),
                        "saved_notes_count": str(len(notes)),
                    },
                )
            )
        return report

    def _generate_base_report(self, workspace_id: str) -> ProjectOverviewReport:
        try:
            return GenerateProjectOverviewReportUseCase(
                workspace_repository=self.workspace_repository,
                project_scan_repository=self.project_scan_repository,
                file_system=self.file_system,
                timeline_repository=None,
            ).execute(GenerateProjectOverviewReportInput(workspace_id=workspace_id))
        except ProjectOverviewReportWorkspaceNotFoundError as exc:
            raise WorkspaceReportNotFoundError("Workspace not found") from exc
        except ProjectOverviewReportScanRequiredError as exc:
            raise WorkspaceReportScanRequiredError(
                "Project scan required before generating workspace reports"
            ) from exc

    def _build_specialized_report(
        self,
        *,
        base_report: ProjectOverviewReport,
        report_type: str,
        notes: list[ConversationAnswerNote],
        conversations: list[WorkspaceConversation],
    ) -> ProjectOverviewReport:
        template = self._template(report_type)
        common_sections = [
            self._source_boundaries_section(),
            self._pick_section(base_report, "Workspace"),
            self._pick_section(base_report, "Detected technologies"),
            self._workspace_context_section(notes, conversations),
        ]
        if report_type == "onboarding_guide":
            sections = common_sections + [
                self._pick_section(base_report, "Application code"),
                self._pick_section(base_report, "Documentation"),
                self._onboarding_steps_section(base_report),
                self._pick_section(base_report, "Recommended next steps"),
            ]
        elif report_type == "devops_review":
            sections = common_sections + [
                self._pick_section(base_report, "Infrastructure"),
                self._pick_section(base_report, "CI/CD"),
                self._pick_section(base_report, "Findings"),
                self._pick_section(base_report, "Suggested commands"),
            ]
        elif report_type == "architecture_summary":
            sections = common_sections + [
                self._pick_section(base_report, "Infrastructure"),
                self._pick_section(base_report, "Application code"),
                self._architecture_notes_section(base_report),
            ]
        elif report_type == "runbook":
            sections = common_sections + [
                self._runbook_checks_section(base_report),
                self._pick_section(base_report, "Suggested commands"),
                self._pick_section(base_report, "Recommended next steps"),
            ]
        else:
            sections = base_report.sections

        return self._finalize_report(
            base_report,
            report_type=report_type,
            title=f"{template.title}: {base_report.title.replace('Project overview: ', '')}",
            summary=f"{template.description} Generated from local workspace context and deterministic scan evidence.",
            sections=sections,
            generated_from=base_report.generated_from + ["saved_answer_notes", "conversation_metadata", f"report_template:{report_type}"],
        )

    def _notes(self, workspace_id: str) -> list[ConversationAnswerNote]:
        if self.conversation_repository is None:
            return []
        return self.conversation_repository.list_answer_notes(workspace_id, limit=10)

    def _conversations(self, workspace_id: str) -> list[WorkspaceConversation]:
        if self.conversation_repository is None:
            return []
        return self.conversation_repository.list_conversations(workspace_id, limit=5)

    @staticmethod
    def _template(report_type: str) -> ReportTemplate:
        return next(template for template in REPORT_TEMPLATES if template.id == report_type)

    @staticmethod
    def _pick_section(report: ProjectOverviewReport, title: str) -> ReportSection:
        return next((section for section in report.sections if section.title == title), ReportSection(title=title, content="No section data is available.", bullets=[]))

    @staticmethod
    def _source_boundaries_section() -> ReportSection:
        return ReportSection(
            title="Source boundaries",
            content="This report is local-first and read-only.",
            bullets=[
                "Generated only from persisted workspace data, latest scan metadata, deterministic analysis, saved notes, and conversation metadata.",
                "No shell commands are executed by report generation.",
                "No scan, index, rebuild, model change, or network upload is triggered by report generation.",
                "Review generated text before using it in tickets, docs, or Confluence.",
            ],
        )

    @staticmethod
    def _workspace_context_section(
        notes: list[ConversationAnswerNote],
        conversations: list[WorkspaceConversation],
    ) -> ReportSection:
        bullets = [
            f"Saved answer notes available: {len(notes)}",
            f"Recent conversations available: {len(conversations)}",
        ]
        for note in notes[:5]:
            source_paths = ", ".join(note.source_paths[:3]) if note.source_paths else "no captured sources"
            bullets.append(f"Note: {note.title}; sources: {source_paths}")
        if len(notes) > 5:
            bullets.append(f"Additional saved notes not shown: {len(notes) - 5}")
        return ReportSection(
            title="Saved workspace context",
            content="Reusable notes and conversation metadata can enrich reports without inventing project facts.",
            bullets=bullets,
        )

    @staticmethod
    def _onboarding_steps_section(base_report: ProjectOverviewReport) -> ReportSection:
        return ReportSection(
            title="Onboarding path",
            content="Suggested learning order for a new contributor.",
            bullets=[
                "Start with the Workspace and Detected technologies sections.",
                "Review README/docs files before asking architecture questions.",
                "Check infrastructure and CI/CD sections before changing deployment workflows.",
                "Use Ask with saved skill profile guidance for follow-up questions grounded in retrieved sources.",
                f"Current report baseline: {base_report.summary}",
            ],
        )

    @staticmethod
    def _architecture_notes_section(base_report: ProjectOverviewReport) -> ReportSection:
        return ReportSection(
            title="Architecture notes",
            content="Architecture claims are intentionally conservative until source files are reviewed.",
            bullets=[
                "Detected technologies indicate candidate components, not guaranteed runtime topology.",
                "Use saved sources and code previews to confirm service boundaries and dependencies.",
                "Promote confirmed findings into reusable notes before generating shareable documentation.",
                f"Evidence baseline: {base_report.summary}",
            ],
        )

    @staticmethod
    def _runbook_checks_section(base_report: ProjectOverviewReport) -> ReportSection:
        return ReportSection(
            title="Operational checklist",
            content="Runbook draft with safe, review-first operational guidance.",
            bullets=[
                "Confirm local runtime health before asking model-backed operational questions.",
                "Review scan/index status before relying on search context.",
                "Use read-only suggested commands as templates only; approve and run manually outside report generation.",
                "Capture validated troubleshooting answers as reusable notes.",
                f"Current deterministic baseline: {base_report.summary}",
            ],
        )

    def _finalize_report(
        self,
        base_report: ProjectOverviewReport,
        *,
        report_type: str,
        title: str,
        summary: str,
        sections: list[ReportSection],
        generated_from: list[str],
    ) -> ProjectOverviewReport:
        report = ProjectOverviewReport(
            workspace_id=base_report.workspace_id,
            title=title,
            summary=summary,
            sections=sections,
            generated_from=list(dict.fromkeys(generated_from)),
            report_type=report_type,
            safety_note=(
                "Report generation is read-only. It does not execute commands, scan, index, rebuild, upload, "
                "or change models. Treat generated text as a draft and verify source-backed claims."
            ),
        )
        return ProjectOverviewReport(
            workspace_id=report.workspace_id,
            title=report.title,
            summary=report.summary,
            sections=report.sections,
            generated_from=report.generated_from,
            report_type=report.report_type,
            export_markdown=render_report_markdown(report),
            safety_note=report.safety_note,
        )


def normalize_report_type(report_type: str) -> str:
    return report_type.strip().lower().replace("-", "_")


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
