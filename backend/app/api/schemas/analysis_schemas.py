from pydantic import BaseModel

from app.core.domain.analysis import AnalysisFinding, TerraformAnalysisResult


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
