from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisFinding:
    id: str
    title: str
    description: str
    severity: str
    evidence: list[str]


@dataclass(frozen=True)
class TerraformAnalysisResult:
    workspace_id: str
    project_path: str
    total_terraform_files: int
    files: list[str]
    has_backend_config: bool
    has_provider_config: bool
    has_variables: bool
    has_outputs: bool
    has_modules: bool
    findings: list[AnalysisFinding]


@dataclass(frozen=True)
class TerragruntAnalysisResult:
    workspace_id: str
    project_path: str
    total_terragrunt_files: int
    files: list[str]
    has_remote_state: bool
    has_include_blocks: bool
    has_dependencies: bool
    has_inputs: bool
    has_terraform_source: bool
    findings: list[AnalysisFinding]


@dataclass(frozen=True)
class GitLabCIJob:
    name: str
    stage: str | None
    image: str | None
    has_rules: bool
    has_only_or_except: bool
    has_artifacts: bool
    has_cache: bool
    has_needs: bool


@dataclass(frozen=True)
class GitLabCIAnalysisResult:
    workspace_id: str
    project_path: str
    file_path: str | None
    stages: list[str]
    includes_count: int
    variables_count: int
    jobs_count: int
    jobs: list[GitLabCIJob]
    findings: list[AnalysisFinding]


@dataclass(frozen=True)
class GitHubActionsWorkflow:
    path: str
    name: str | None
    triggers: list[str]
    jobs_count: int
    uses_reusable_workflows: bool
    uses_matrix: bool
    uses_permissions: bool
    has_secrets_reference: bool


@dataclass(frozen=True)
class GitHubActionsAnalysisResult:
    workspace_id: str
    project_path: str
    workflow_files_count: int
    workflows: list[GitHubActionsWorkflow]
    total_jobs_count: int
    findings: list[AnalysisFinding]
