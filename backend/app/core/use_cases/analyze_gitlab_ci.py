from dataclasses import dataclass
from typing import Any

import yaml

from app.core.domain.analysis import (
    AnalysisFinding,
    GitLabCIAnalysisResult,
    GitLabCIJob,
)
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

RESERVED_GITLAB_KEYS = {
    "stages",
    "include",
    "variables",
    "workflow",
    "default",
    "image",
    "services",
    "before_script",
    "after_script",
    "cache",
}


@dataclass(frozen=True)
class AnalyzeGitLabCIInput:
    workspace_id: str


class GitLabCIAnalysisWorkspaceNotFoundError(ValueError):
    pass


class GitLabCIAnalysisScanRequiredError(ValueError):
    pass


class AnalyzeGitLabCIUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzeGitLabCIInput) -> GitLabCIAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise GitLabCIAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise GitLabCIAnalysisScanRequiredError("Project scan required before analysis")

        gitlab_ci_file = next(
            (
                project_file
                for project_file in latest_scan.files
                if project_file.detected_type == "gitlab_ci"
            ),
            None,
        )

        if gitlab_ci_file is None:
            return self._without_gitlab_ci_file(workspace.id, workspace.project_path)

        content = self.file_system.read_text_file(
            root_path=workspace.project_path,
            relative_path=gitlab_ci_file.path,
        )

        try:
            parsed_yaml = yaml.safe_load(content) or {}
        except yaml.YAMLError as exc:
            return self._with_parse_error(
                workspace_id=workspace.id,
                project_path=workspace.project_path,
                file_path=gitlab_ci_file.path,
                error=str(exc),
            )

        if not isinstance(parsed_yaml, dict):
            return self._with_parse_error(
                workspace_id=workspace.id,
                project_path=workspace.project_path,
                file_path=gitlab_ci_file.path,
                error="GitLab CI YAML root must be a mapping.",
            )

        stages = self._parse_stages(parsed_yaml.get("stages"))
        jobs = self._parse_jobs(parsed_yaml)
        findings = self._build_findings(
            file_path=gitlab_ci_file.path,
            parsed_yaml=parsed_yaml,
            stages=stages,
            jobs=jobs,
        )

        return GitLabCIAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            file_path=gitlab_ci_file.path,
            stages=stages,
            includes_count=self._count_includes(parsed_yaml.get("include")),
            variables_count=self._count_variables(parsed_yaml.get("variables")),
            jobs_count=len(jobs),
            jobs=jobs,
            findings=findings,
        )

    @staticmethod
    def _without_gitlab_ci_file(
        workspace_id: str,
        project_path: str,
    ) -> GitLabCIAnalysisResult:
        return GitLabCIAnalysisResult(
            workspace_id=workspace_id,
            project_path=project_path,
            file_path=None,
            stages=[],
            includes_count=0,
            variables_count=0,
            jobs_count=0,
            jobs=[],
            findings=[
                AnalysisFinding(
                    id="gitlab_ci_no_file",
                    title="No GitLab CI file found",
                    description="The latest project scan did not detect a .gitlab-ci.yml file.",
                    severity="info",
                    evidence=[],
                )
            ],
        )

    @staticmethod
    def _with_parse_error(
        workspace_id: str,
        project_path: str,
        file_path: str,
        error: str,
    ) -> GitLabCIAnalysisResult:
        return GitLabCIAnalysisResult(
            workspace_id=workspace_id,
            project_path=project_path,
            file_path=file_path,
            stages=[],
            includes_count=0,
            variables_count=0,
            jobs_count=0,
            jobs=[],
            findings=[
                AnalysisFinding(
                    id="gitlab_ci_yaml_parse_error",
                    title="GitLab CI YAML parse error",
                    description=f"Unable to parse GitLab CI YAML: {error}",
                    severity="high",
                    evidence=[file_path],
                )
            ],
        )

    @staticmethod
    def _parse_stages(raw_stages: Any) -> list[str]:
        if not isinstance(raw_stages, list):
            return []
        return [stage for stage in raw_stages if isinstance(stage, str)]

    def _parse_jobs(self, parsed_yaml: dict[str, Any]) -> list[GitLabCIJob]:
        jobs: list[GitLabCIJob] = []

        for key, value in parsed_yaml.items():
            if key in RESERVED_GITLAB_KEYS or not isinstance(value, dict):
                continue

            jobs.append(
                GitLabCIJob(
                    name=key,
                    stage=self._string_or_none(value.get("stage")),
                    image=self._parse_image(value.get("image")),
                    has_rules="rules" in value,
                    has_only_or_except="only" in value or "except" in value,
                    has_artifacts="artifacts" in value,
                    has_cache="cache" in value,
                    has_needs="needs" in value,
                )
            )

        return jobs

    @staticmethod
    def _parse_image(raw_image: Any) -> str | None:
        if isinstance(raw_image, str):
            return raw_image
        if isinstance(raw_image, dict) and isinstance(raw_image.get("name"), str):
            return raw_image["name"]
        return None

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _count_includes(raw_include: Any) -> int:
        if raw_include is None:
            return 0
        if isinstance(raw_include, list):
            return len(raw_include)
        return 1

    @staticmethod
    def _count_variables(raw_variables: Any) -> int:
        if not isinstance(raw_variables, dict):
            return 0
        return len(raw_variables)

    def _build_findings(
        self,
        file_path: str,
        parsed_yaml: dict[str, Any],
        stages: list[str],
        jobs: list[GitLabCIJob],
    ) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []

        if not stages:
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_stages_missing",
                    title="Stages not defined",
                    description="No top-level GitLab CI stages list was found.",
                    severity="medium",
                    evidence=[file_path],
                )
            )

        if not jobs:
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_jobs_missing",
                    title="No jobs found",
                    description="No top-level GitLab CI jobs were detected.",
                    severity="high",
                    evidence=[file_path],
                )
            )

        jobs_without_stage = [job.name for job in jobs if job.stage is None]
        if jobs_without_stage:
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_jobs_without_stage",
                    title="Jobs without stage",
                    description="Some GitLab CI jobs do not define an explicit stage.",
                    severity="low",
                    evidence=jobs_without_stage,
                )
            )

        only_or_except_jobs = [job.name for job in jobs if job.has_only_or_except]
        if only_or_except_jobs:
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_only_except_used",
                    title="only/except detected",
                    description="Some jobs use only/except; consider rules for newer GitLab CI conditions.",
                    severity="medium",
                    evidence=only_or_except_jobs,
                )
            )

        if not self._has_workflow_rules(parsed_yaml):
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_workflow_rules_missing",
                    title="Workflow rules not detected",
                    description="No top-level workflow rules were found.",
                    severity="low",
                    evidence=[file_path],
                )
            )

        top_level_cache = "cache" in parsed_yaml
        if not top_level_cache and not any(job.has_cache for job in jobs):
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_cache_missing",
                    title="Cache not detected",
                    description="No top-level or job-level cache configuration was found.",
                    severity="low",
                    evidence=[file_path],
                )
            )

        artifacts_jobs = [job.name for job in jobs if job.has_artifacts]
        if artifacts_jobs:
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_artifacts_detected",
                    title="Artifacts detected",
                    description="One or more jobs publish artifacts.",
                    severity="info",
                    evidence=artifacts_jobs,
                )
            )

        needs_jobs = [job.name for job in jobs if job.has_needs]
        if needs_jobs:
            findings.append(
                AnalysisFinding(
                    id="gitlab_ci_needs_detected",
                    title="Needs detected",
                    description="One or more jobs use needs dependencies.",
                    severity="info",
                    evidence=needs_jobs,
                )
            )

        return findings

    @staticmethod
    def _has_workflow_rules(parsed_yaml: dict[str, Any]) -> bool:
        workflow = parsed_yaml.get("workflow")
        return isinstance(workflow, dict) and "rules" in workflow
