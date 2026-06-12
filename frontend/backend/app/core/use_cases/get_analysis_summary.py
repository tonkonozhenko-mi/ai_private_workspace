from dataclasses import dataclass
from typing import Callable

from app.core.domain.analysis import (
    AnalysisFinding,
    AnalysisSummaryResult,
    AnalyzerStatus,
    SeverityCounts,
)
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.workspace import Workspace
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.analyze_github_actions import (
    AnalyzeGitHubActionsInput,
    AnalyzeGitHubActionsUseCase,
)
from app.core.use_cases.analyze_gitlab_ci import (
    AnalyzeGitLabCIInput,
    AnalyzeGitLabCIUseCase,
)
from app.core.use_cases.analyze_terraform import (
    AnalyzeTerraformInput,
    AnalyzeTerraformUseCase,
)
from app.core.use_cases.analyze_terragrunt import (
    AnalyzeTerragruntInput,
    AnalyzeTerragruntUseCase,
)


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


@dataclass(frozen=True)
class GetAnalysisSummaryInput:
    workspace_id: str


@dataclass(frozen=True)
class AnalyzerDefinition:
    name: str
    detected_type: str
    run: Callable[[str], list[AnalysisFinding]]


class AnalysisSummaryWorkspaceNotFoundError(ValueError):
    pass


class GetAnalysisSummaryUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: GetAnalysisSummaryInput) -> AnalysisSummaryResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise AnalysisSummaryWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            return self._without_scan(workspace)

        return self._with_scan(workspace, latest_scan)

    def _without_scan(self, workspace: Workspace) -> AnalysisSummaryResult:
        return AnalysisSummaryResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            has_scan=False,
            analyzers=[],
            severity_counts=SeverityCounts(info=0, low=0, medium=0, high=0),
            total_findings=0,
            top_findings=[],
            recommended_next_steps=["Run project scan first."],
        )

    def _with_scan(
        self,
        workspace: Workspace,
        latest_scan: ProjectScanResult,
    ) -> AnalysisSummaryResult:
        detected_types = {project_file.detected_type for project_file in latest_scan.files}
        findings: list[AnalysisFinding] = []
        analyzer_statuses: list[AnalyzerStatus] = []

        for analyzer in self._analyzers():
            if analyzer.detected_type not in detected_types:
                analyzer_statuses.append(
                    AnalyzerStatus(
                        name=analyzer.name,
                        status="skipped",
                        reason="Relevant files not detected.",
                        findings_count=0,
                    )
                )
                continue

            try:
                analyzer_findings = analyzer.run(workspace.id)
            except Exception as exc:
                analyzer_statuses.append(
                    AnalyzerStatus(
                        name=analyzer.name,
                        status="failed",
                        reason=str(exc),
                        findings_count=0,
                    )
                )
                continue

            findings.extend(analyzer_findings)
            analyzer_statuses.append(
                AnalyzerStatus(
                    name=analyzer.name,
                    status="completed",
                    reason=None,
                    findings_count=len(analyzer_findings),
                )
            )

        severity_counts = self._count_severities(findings)

        return AnalysisSummaryResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            has_scan=True,
            analyzers=analyzer_statuses,
            severity_counts=severity_counts,
            total_findings=len(findings),
            top_findings=self._top_findings(findings),
            recommended_next_steps=self._recommended_next_steps(
                severity_counts=severity_counts,
                detected_types=detected_types,
                total_findings=len(findings),
            ),
        )

    def _analyzers(self) -> list[AnalyzerDefinition]:
        terraform_use_case = AnalyzeTerraformUseCase(
            workspace_repository=self.workspace_repository,
            project_scan_repository=self.project_scan_repository,
            file_system=self.file_system,
        )
        terragrunt_use_case = AnalyzeTerragruntUseCase(
            workspace_repository=self.workspace_repository,
            project_scan_repository=self.project_scan_repository,
            file_system=self.file_system,
        )
        gitlab_ci_use_case = AnalyzeGitLabCIUseCase(
            workspace_repository=self.workspace_repository,
            project_scan_repository=self.project_scan_repository,
            file_system=self.file_system,
        )
        github_actions_use_case = AnalyzeGitHubActionsUseCase(
            workspace_repository=self.workspace_repository,
            project_scan_repository=self.project_scan_repository,
            file_system=self.file_system,
        )

        return [
            AnalyzerDefinition(
                name="Terraform",
                detected_type="terraform",
                run=lambda workspace_id: terraform_use_case.execute(
                    AnalyzeTerraformInput(workspace_id=workspace_id)
                ).findings,
            ),
            AnalyzerDefinition(
                name="Terragrunt",
                detected_type="terragrunt",
                run=lambda workspace_id: terragrunt_use_case.execute(
                    AnalyzeTerragruntInput(workspace_id=workspace_id)
                ).findings,
            ),
            AnalyzerDefinition(
                name="GitLab CI",
                detected_type="gitlab_ci",
                run=lambda workspace_id: gitlab_ci_use_case.execute(
                    AnalyzeGitLabCIInput(workspace_id=workspace_id)
                ).findings,
            ),
            AnalyzerDefinition(
                name="GitHub Actions",
                detected_type="github_actions",
                run=lambda workspace_id: github_actions_use_case.execute(
                    AnalyzeGitHubActionsInput(workspace_id=workspace_id)
                ).findings,
            ),
        ]

    @staticmethod
    def _count_severities(findings: list[AnalysisFinding]) -> SeverityCounts:
        return SeverityCounts(
            info=sum(1 for finding in findings if finding.severity == "info"),
            low=sum(1 for finding in findings if finding.severity == "low"),
            medium=sum(1 for finding in findings if finding.severity == "medium"),
            high=sum(1 for finding in findings if finding.severity == "high"),
        )

    @staticmethod
    def _top_findings(findings: list[AnalysisFinding]) -> list[AnalysisFinding]:
        return sorted(
            findings,
            key=lambda finding: SEVERITY_ORDER.get(finding.severity, 99),
        )[:10]

    @staticmethod
    def _recommended_next_steps(
        severity_counts: SeverityCounts,
        detected_types: set[str],
        total_findings: int,
    ) -> list[str]:
        next_steps: list[str] = []

        if severity_counts.high:
            next_steps.append("Review high severity findings first.")
        if severity_counts.medium:
            next_steps.append(
                "Review medium severity findings and decide whether they require changes."
            )
        if {"terraform", "terragrunt"}.intersection(detected_types):
            next_steps.append("Review infrastructure configuration and state management.")
        if {"gitlab_ci", "github_actions"}.intersection(detected_types):
            next_steps.append("Review CI/CD workflow structure and permissions.")
        if total_findings == 0:
            next_steps.append(
                "No deterministic issues found. Consider generating an AI-assisted project overview."
            )

        return next_steps
