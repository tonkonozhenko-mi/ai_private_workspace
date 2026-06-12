from dataclasses import dataclass

from app.core.domain.analysis import AnalysisSummaryResult
from app.core.domain.command_suggestion import CommandSuggestion
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.report import ProjectOverviewReport, ReportSection
from app.core.domain.skill import SkillMatch
from app.core.domain.workspace import Workspace
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)
from app.core.use_cases.get_analysis_summary import (
    GetAnalysisSummaryInput,
    GetAnalysisSummaryUseCase,
)
from app.core.use_cases.suggest_workspace_commands import (
    SuggestWorkspaceCommandsInput,
    SuggestWorkspaceCommandsUseCase,
)


@dataclass(frozen=True)
class GenerateProjectOverviewReportInput:
    workspace_id: str


class ProjectOverviewReportWorkspaceNotFoundError(ValueError):
    pass


class ProjectOverviewReportScanRequiredError(ValueError):
    pass


class GenerateProjectOverviewReportUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        self.timeline_repository = timeline_repository

    def execute(
        self,
        request: GenerateProjectOverviewReportInput,
    ) -> ProjectOverviewReport:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise ProjectOverviewReportWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise ProjectOverviewReportScanRequiredError(
                "Project scan required before generating project overview report"
            )

        analysis_summary = GetAnalysisSummaryUseCase(
            workspace_repository=self.workspace_repository,
            project_scan_repository=self.project_scan_repository,
            file_system=self.file_system,
        ).execute(GetAnalysisSummaryInput(workspace_id=request.workspace_id))
        command_suggestions = SuggestWorkspaceCommandsUseCase(
            workspace_repository=self.workspace_repository,
            project_scan_repository=self.project_scan_repository,
        ).execute(SuggestWorkspaceCommandsInput(workspace_id=request.workspace_id))

        sections = [
            self._workspace_section(workspace),
            self._detected_technologies_section(latest_scan),
            self._infrastructure_section(latest_scan.detected_skills),
            self._cicd_section(latest_scan.detected_skills),
            self._application_code_section(latest_scan.detected_skills),
            self._documentation_section(latest_scan.detected_skills),
            self._findings_section(analysis_summary),
            self._recommended_next_steps_section(analysis_summary),
            self._suggested_commands_section(command_suggestions),
        ]

        report = ProjectOverviewReport(
            workspace_id=workspace.id,
            title=f"Project overview: {workspace.name}",
            summary=self._summary(workspace, latest_scan, analysis_summary),
            sections=sections,
            generated_from=[
                "latest_project_scan",
                "analysis_summary",
                "command_suggestions",
                "deterministic_rules",
            ],
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=workspace.id,
                    event_type="project_overview_generated",
                    title="Project overview generated",
                    summary="Generated a deterministic project overview report.",
                    metadata={"sections_count": str(len(report.sections))},
                )
            )
        return report

    @staticmethod
    def _summary(
        workspace: Workspace,
        latest_scan: ProjectScanResult,
        analysis_summary: AnalysisSummaryResult,
    ) -> str:
        return (
            f"{workspace.name} has {latest_scan.scanned_files} scanned files, "
            f"{latest_scan.skipped_files} skipped files, "
            f"{len(latest_scan.detected_skills)} detected technologies, and "
            f"{analysis_summary.total_findings} deterministic findings."
        )

    @staticmethod
    def _workspace_section(workspace: Workspace) -> ReportSection:
        return ReportSection(
            title="Workspace",
            content="Workspace metadata from the persisted workspace record.",
            bullets=[
                f"Name: {workspace.name}",
                f"Project path: {workspace.project_path}",
                f"Assistant mode: {workspace.assistant_mode}",
                f"Privacy mode: {workspace.privacy_mode}",
            ],
        )

    def _detected_technologies_section(
        self,
        latest_scan: ProjectScanResult,
    ) -> ReportSection:
        grouped_skills = self._skills_by_category(latest_scan.detected_skills)
        category_order = [
            "devops",
            "developer",
            "qa",
            "documentation",
            "manager",
            "general",
        ]
        bullets: list[str] = []

        for category in category_order:
            skills = grouped_skills.pop(category, [])
            if skills:
                bullets.append(f"{category}: {self._skill_names(skills)}")

        for category in sorted(grouped_skills):
            bullets.append(f"{category}: {self._skill_names(grouped_skills[category])}")

        if not bullets:
            bullets.append("No technologies detected.")

        return ReportSection(
            title="Detected technologies",
            content=(
                "Technologies are grouped by Skill Registry category from the "
                "latest deterministic project scan."
            ),
            bullets=bullets,
        )

    def _infrastructure_section(self, skills: list[SkillMatch]) -> ReportSection:
        return self._skill_section(
            title="Infrastructure",
            content_when_present=(
                "Infrastructure-related technologies were detected in the workspace."
            ),
            content_when_absent=(
                "No Terraform, Terragrunt, Kubernetes, or Helm signals were detected."
            ),
            skill_names=["Terraform", "Terragrunt", "Kubernetes", "Helm"],
            skills=skills,
        )

    def _cicd_section(self, skills: list[SkillMatch]) -> ReportSection:
        return self._skill_section(
            title="CI/CD",
            content_when_present="CI/CD automation files were detected in the workspace.",
            content_when_absent="No GitLab CI or GitHub Actions files were detected.",
            skill_names=["GitLab CI", "GitHub Actions"],
            skills=skills,
        )

    def _application_code_section(self, skills: list[SkillMatch]) -> ReportSection:
        developer_skills = [
            skill for skill in skills if skill.category == "developer"
        ]
        bullets = [
            self._skill_bullet(skill)
            for skill in sorted(developer_skills, key=lambda skill: skill.name)
        ]
        if not bullets:
            bullets.append("No developer language or framework signals were detected.")

        return ReportSection(
            title="Application code",
            content=(
                "Developer-oriented skills are summarized from deterministic file "
                "signals."
                if developer_skills
                else "No application-code skill signals were detected."
            ),
            bullets=bullets,
        )

    def _documentation_section(self, skills: list[SkillMatch]) -> ReportSection:
        return self._skill_section(
            title="Documentation",
            content_when_present="Markdown documentation was detected in the workspace.",
            content_when_absent="No Markdown documentation was detected.",
            skill_names=["Documentation"],
            skills=skills,
        )

    @staticmethod
    def _findings_section(analysis_summary: AnalysisSummaryResult) -> ReportSection:
        severity_counts = analysis_summary.severity_counts
        bullets = [
            (
                f"{finding.severity}: {finding.title} - "
                f"{finding.description}"
            )
            for finding in analysis_summary.top_findings
        ]
        if not bullets:
            bullets.append("No deterministic findings were reported.")

        return ReportSection(
            title="Findings",
            content=(
                f"Deterministic analyzers reported "
                f"{analysis_summary.total_findings} findings: "
                f"{severity_counts.high} high, "
                f"{severity_counts.medium} medium, "
                f"{severity_counts.low} low, and "
                f"{severity_counts.info} info."
            ),
            bullets=bullets,
        )

    @staticmethod
    def _recommended_next_steps_section(
        analysis_summary: AnalysisSummaryResult,
    ) -> ReportSection:
        bullets = analysis_summary.recommended_next_steps or [
            "No recommended next steps were generated."
        ]
        return ReportSection(
            title="Recommended next steps",
            content="Next steps are generated from deterministic analysis findings.",
            bullets=bullets,
        )

    @staticmethod
    def _suggested_commands_section(
        command_suggestions: list[CommandSuggestion],
    ) -> ReportSection:
        readonly_suggestions = [
            suggestion
            for suggestion in command_suggestions
            if suggestion.risk == "readonly"
        ][:5]
        bullets = [
            f"{suggestion.title}: {suggestion.command}"
            for suggestion in readonly_suggestions
        ]
        if not bullets:
            bullets.append("No read-only command suggestions are available.")

        return ReportSection(
            title="Suggested commands",
            content=(
                "Suggested commands are templates only. They are not proposed, "
                "approved, or executed by this report."
            ),
            bullets=bullets,
        )

    def _skill_section(
        self,
        title: str,
        content_when_present: str,
        content_when_absent: str,
        skill_names: list[str],
        skills: list[SkillMatch],
    ) -> ReportSection:
        skill_map = {skill.name: skill for skill in skills}
        matched_skills = [
            skill_map[skill_name]
            for skill_name in skill_names
            if skill_name in skill_map
        ]
        bullets = [self._skill_bullet(skill) for skill in matched_skills]
        if not bullets:
            bullets.append(content_when_absent)

        return ReportSection(
            title=title,
            content=content_when_present if matched_skills else content_when_absent,
            bullets=bullets,
        )

    @staticmethod
    def _skills_by_category(skills: list[SkillMatch]) -> dict[str, list[SkillMatch]]:
        grouped_skills: dict[str, list[SkillMatch]] = {}
        for skill in skills:
            grouped_skills.setdefault(skill.category, []).append(skill)
        return grouped_skills

    @staticmethod
    def _skill_names(skills: list[SkillMatch]) -> str:
        return ", ".join(skill.name for skill in sorted(skills, key=lambda skill: skill.name))

    @staticmethod
    def _skill_bullet(skill: SkillMatch) -> str:
        evidence = ", ".join(skill.evidence[:3]) if skill.evidence else "no evidence"
        return f"{skill.name}: {skill.confidence} confidence; evidence: {evidence}"
