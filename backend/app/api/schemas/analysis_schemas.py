from pydantic import BaseModel

from app.core.domain.analysis import (
    AnalysisFinding,
    GitLabCIAnalysisResult,
    GitLabCIJob,
    TerraformAnalysisResult,
    TerragruntAnalysisResult,
)


class AnalysisFindingResponse(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    evidence: list[str]


class TerraformAnalysisResponse(BaseModel):
    workspace_id: str
    project_path: str
    total_terraform_files: int
    files: list[str]
    has_backend_config: bool
    has_provider_config: bool
    has_variables: bool
    has_outputs: bool
    has_modules: bool
    findings: list[AnalysisFindingResponse]


class TerragruntAnalysisResponse(BaseModel):
    workspace_id: str
    project_path: str
    total_terragrunt_files: int
    files: list[str]
    has_remote_state: bool
    has_include_blocks: bool
    has_dependencies: bool
    has_inputs: bool
    has_terraform_source: bool
    findings: list[AnalysisFindingResponse]


class GitLabCIJobResponse(BaseModel):
    name: str
    stage: str | None
    image: str | None
    has_rules: bool
    has_only_or_except: bool
    has_artifacts: bool
    has_cache: bool
    has_needs: bool


class GitLabCIAnalysisResponse(BaseModel):
    workspace_id: str
    project_path: str
    file_path: str | None
    stages: list[str]
    includes_count: int
    variables_count: int
    jobs_count: int
    jobs: list[GitLabCIJobResponse]
    findings: list[AnalysisFindingResponse]


def to_analysis_finding_response(
    finding: AnalysisFinding,
) -> AnalysisFindingResponse:
    return AnalysisFindingResponse(
        id=finding.id,
        title=finding.title,
        description=finding.description,
        severity=finding.severity,
        evidence=finding.evidence,
    )


def to_terraform_analysis_response(
    result: TerraformAnalysisResult,
) -> TerraformAnalysisResponse:
    return TerraformAnalysisResponse(
        workspace_id=result.workspace_id,
        project_path=result.project_path,
        total_terraform_files=result.total_terraform_files,
        files=result.files,
        has_backend_config=result.has_backend_config,
        has_provider_config=result.has_provider_config,
        has_variables=result.has_variables,
        has_outputs=result.has_outputs,
        has_modules=result.has_modules,
        findings=[
            to_analysis_finding_response(finding) for finding in result.findings
        ],
    )


def to_terragrunt_analysis_response(
    result: TerragruntAnalysisResult,
) -> TerragruntAnalysisResponse:
    return TerragruntAnalysisResponse(
        workspace_id=result.workspace_id,
        project_path=result.project_path,
        total_terragrunt_files=result.total_terragrunt_files,
        files=result.files,
        has_remote_state=result.has_remote_state,
        has_include_blocks=result.has_include_blocks,
        has_dependencies=result.has_dependencies,
        has_inputs=result.has_inputs,
        has_terraform_source=result.has_terraform_source,
        findings=[
            to_analysis_finding_response(finding) for finding in result.findings
        ],
    )


def to_gitlab_ci_job_response(job: GitLabCIJob) -> GitLabCIJobResponse:
    return GitLabCIJobResponse(
        name=job.name,
        stage=job.stage,
        image=job.image,
        has_rules=job.has_rules,
        has_only_or_except=job.has_only_or_except,
        has_artifacts=job.has_artifacts,
        has_cache=job.has_cache,
        has_needs=job.has_needs,
    )


def to_gitlab_ci_analysis_response(
    result: GitLabCIAnalysisResult,
) -> GitLabCIAnalysisResponse:
    return GitLabCIAnalysisResponse(
        workspace_id=result.workspace_id,
        project_path=result.project_path,
        file_path=result.file_path,
        stages=result.stages,
        includes_count=result.includes_count,
        variables_count=result.variables_count,
        jobs_count=result.jobs_count,
        jobs=[to_gitlab_ci_job_response(job) for job in result.jobs],
        findings=[
            to_analysis_finding_response(finding) for finding in result.findings
        ],
    )
