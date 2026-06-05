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
