from dataclasses import dataclass
from typing import Any

import yaml

from app.core.domain.analysis import (
    AnalysisFinding,
    GitHubActionsAnalysisResult,
    GitHubActionsWorkflow,
)
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class AnalyzeGitHubActionsInput:
    workspace_id: str


class GitHubActionsAnalysisWorkspaceNotFoundError(ValueError):
    pass


class GitHubActionsAnalysisScanRequiredError(ValueError):
    pass


class AnalyzeGitHubActionsUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzeGitHubActionsInput) -> GitHubActionsAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise GitHubActionsAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise GitHubActionsAnalysisScanRequiredError("Project scan required before analysis")

        workflow_files = [
            project_file
            for project_file in latest_scan.files
            if project_file.detected_type == "github_actions"
        ]

        if not workflow_files:
            return GitHubActionsAnalysisResult(
                workspace_id=workspace.id,
                project_path=workspace.project_path,
                workflow_files_count=0,
                workflows=[],
                total_jobs_count=0,
                findings=[
                    AnalysisFinding(
                        id="github_actions_no_workflows",
                        title="No GitHub Actions workflows found",
                        description="The latest project scan did not detect GitHub Actions workflow files.",
                        severity="info",
                        evidence=[],
                    )
                ],
            )

        workflows: list[GitHubActionsWorkflow] = []
        findings: list[AnalysisFinding] = []

        for workflow_file in workflow_files:
            content = self.file_system.read_text_file(
                root_path=workspace.project_path,
                relative_path=workflow_file.path,
            )
            try:
                parsed_yaml = yaml.safe_load(content) or {}
            except yaml.YAMLError as exc:
                findings.append(self._parse_error_finding(workflow_file.path, str(exc)))
                continue

            if not isinstance(parsed_yaml, dict):
                findings.append(
                    self._parse_error_finding(
                        workflow_file.path,
                        "GitHub Actions YAML root must be a mapping.",
                    )
                )
                continue

            workflow = self._parse_workflow(
                path=workflow_file.path,
                parsed_yaml=parsed_yaml,
                content=content,
            )
            workflows.append(workflow)
            findings.extend(self._build_workflow_findings(workflow))

        return GitHubActionsAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            workflow_files_count=len(workflow_files),
            workflows=workflows,
            total_jobs_count=sum(workflow.jobs_count for workflow in workflows),
            findings=findings,
        )

    @staticmethod
    def _parse_workflow(
        path: str,
        parsed_yaml: dict[Any, Any],
        content: str,
    ) -> GitHubActionsWorkflow:
        jobs = parsed_yaml.get("jobs")
        jobs_mapping = jobs if isinstance(jobs, dict) else {}
        job_values = [value for value in jobs_mapping.values() if isinstance(value, dict)]
        job_names = [str(key) for key in jobs_mapping.keys()]

        return GitHubActionsWorkflow(
            path=path,
            name=parsed_yaml["name"] if isinstance(parsed_yaml.get("name"), str) else None,
            triggers=AnalyzeGitHubActionsUseCase._parse_triggers(parsed_yaml),
            jobs_count=len(jobs_mapping),
            job_names=job_names,
            uses_reusable_workflows=any("uses" in job for job in job_values),
            uses_matrix=any(
                isinstance(job.get("strategy"), dict)
                and isinstance(job["strategy"].get("matrix"), dict)
                for job in job_values
            ),
            uses_permissions="permissions" in parsed_yaml
            or any("permissions" in job for job in job_values),
            has_secrets_reference="secrets." in content,
        )

    @staticmethod
    def _parse_triggers(parsed_yaml: dict[Any, Any]) -> list[str]:
        raw_triggers = parsed_yaml.get("on")
        if raw_triggers is None and True in parsed_yaml:
            raw_triggers = parsed_yaml[True]

        if isinstance(raw_triggers, str):
            return [raw_triggers]
        if isinstance(raw_triggers, list):
            return [trigger for trigger in raw_triggers if isinstance(trigger, str)]
        if isinstance(raw_triggers, dict):
            return [str(trigger) for trigger in raw_triggers.keys()]

        return []

    @staticmethod
    def _parse_error_finding(path: str, error: str) -> AnalysisFinding:
        return AnalysisFinding(
            id="github_actions_yaml_parse_error",
            title="GitHub Actions YAML parse error",
            description=f"Unable to parse GitHub Actions YAML: {error}",
            severity="high",
            evidence=[path],
        )

    @staticmethod
    def _build_workflow_findings(
        workflow: GitHubActionsWorkflow,
    ) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []

        if not workflow.triggers:
            findings.append(
                AnalysisFinding(
                    id="github_actions_triggers_missing",
                    title="Workflow triggers not detected",
                    description="No GitHub Actions workflow triggers were detected.",
                    severity="medium",
                    evidence=[workflow.path],
                )
            )

        if workflow.jobs_count == 0:
            findings.append(
                AnalysisFinding(
                    id="github_actions_jobs_missing",
                    title="No jobs found",
                    description="No jobs were detected in the workflow.",
                    severity="high",
                    evidence=[workflow.path],
                )
            )

        if not workflow.uses_permissions:
            findings.append(
                AnalysisFinding(
                    id="github_actions_permissions_missing",
                    title="Permissions not configured",
                    description="No top-level or job-level permissions block was detected.",
                    severity="medium",
                    evidence=[workflow.path],
                )
            )

        if workflow.has_secrets_reference:
            findings.append(
                AnalysisFinding(
                    id="github_actions_secrets_referenced",
                    title="Secrets referenced",
                    description="The workflow references GitHub Actions secrets.",
                    severity="info",
                    evidence=[workflow.path],
                )
            )

        if workflow.uses_matrix:
            findings.append(
                AnalysisFinding(
                    id="github_actions_matrix_detected",
                    title="Matrix strategy detected",
                    description="The workflow uses a matrix strategy.",
                    severity="info",
                    evidence=[workflow.path],
                )
            )

        if workflow.uses_reusable_workflows:
            findings.append(
                AnalysisFinding(
                    id="github_actions_reusable_workflows_detected",
                    title="Reusable workflows detected",
                    description="The workflow uses reusable workflow jobs.",
                    severity="info",
                    evidence=[workflow.path],
                )
            )

        return findings
