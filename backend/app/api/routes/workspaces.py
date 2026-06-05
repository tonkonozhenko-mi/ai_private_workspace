from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    command_repository,
    file_system,
    project_scan_repository,
    workspace_repository,
)
from app.api.project_scan_schemas import ProjectScanResponse, to_project_scan_response
from app.api.schemas.analysis_schemas import (
    AnalysisSummaryResponse,
    GitHubActionsAnalysisResponse,
    GitLabCIAnalysisResponse,
    TerraformAnalysisResponse,
    TerragruntAnalysisResponse,
    to_analysis_summary_response,
    to_github_actions_analysis_response,
    to_gitlab_ci_analysis_response,
    to_terraform_analysis_response,
    to_terragrunt_analysis_response,
)
from app.api.schemas.report_schemas import (
    ProjectOverviewReportResponse,
    to_project_overview_report_response,
)
from app.api.schemas.workspace_summary_schemas import (
    WorkspaceSummaryResponse,
    to_workspace_summary_response,
)
from app.core.domain.workspace import Workspace
from app.core.use_cases.analyze_github_actions import (
    AnalyzeGitHubActionsInput,
    AnalyzeGitHubActionsUseCase,
    GitHubActionsAnalysisScanRequiredError,
    GitHubActionsAnalysisWorkspaceNotFoundError,
)
from app.core.use_cases.analyze_gitlab_ci import (
    AnalyzeGitLabCIInput,
    AnalyzeGitLabCIUseCase,
    GitLabCIAnalysisScanRequiredError,
    GitLabCIAnalysisWorkspaceNotFoundError,
)
from app.core.use_cases.analyze_terraform import (
    AnalyzeTerraformInput,
    AnalyzeTerraformUseCase,
    TerraformAnalysisScanRequiredError,
    TerraformAnalysisWorkspaceNotFoundError,
)
from app.core.use_cases.analyze_terragrunt import (
    AnalyzeTerragruntInput,
    AnalyzeTerragruntUseCase,
    TerragruntAnalysisScanRequiredError,
    TerragruntAnalysisWorkspaceNotFoundError,
)
from app.core.use_cases.create_workspace import (
    CreateWorkspaceInput,
    CreateWorkspaceUseCase,
)
from app.core.use_cases.get_workspace_latest_scan import (
    GetWorkspaceLatestScanInput,
    GetWorkspaceLatestScanUseCase,
)
from app.core.use_cases.get_analysis_summary import (
    AnalysisSummaryWorkspaceNotFoundError,
    GetAnalysisSummaryInput,
    GetAnalysisSummaryUseCase,
)
from app.core.use_cases.generate_project_overview_report import (
    GenerateProjectOverviewReportInput,
    GenerateProjectOverviewReportUseCase,
    ProjectOverviewReportScanRequiredError,
    ProjectOverviewReportWorkspaceNotFoundError,
)
from app.core.use_cases.get_workspace import GetWorkspaceUseCase
from app.core.use_cases.get_workspace_summary import (
    GetWorkspaceSummaryInput,
    GetWorkspaceSummaryUseCase,
    WorkspaceSummaryNotFoundError,
)
from app.core.use_cases.list_workspaces import ListWorkspacesUseCase
from app.core.use_cases.scan_project import ProjectScanError
from app.core.use_cases.scan_workspace_project import (
    ScanWorkspaceProjectInput,
    ScanWorkspaceProjectUseCase,
    WorkspaceNotFoundError,
)


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1)
    project_path: str = Field(..., min_length=1)
    assistant_mode: str = Field(default="local")
    privacy_mode: str = Field(default="private")


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: datetime


def to_workspace_response(workspace: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        project_path=workspace.project_path,
        assistant_mode=workspace.assistant_mode,
        privacy_mode=workspace.privacy_mode,
        created_at=workspace.created_at,
    )


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(request: CreateWorkspaceRequest) -> WorkspaceResponse:
    use_case = CreateWorkspaceUseCase(workspace_repository)
    workspace = use_case.execute(
        CreateWorkspaceInput(
            name=request.name,
            project_path=request.project_path,
            assistant_mode=request.assistant_mode,
            privacy_mode=request.privacy_mode,
        )
    )
    return to_workspace_response(workspace)


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces() -> list[WorkspaceResponse]:
    use_case = ListWorkspacesUseCase(workspace_repository)
    return [to_workspace_response(workspace) for workspace in use_case.execute()]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: str) -> WorkspaceResponse:
    use_case = GetWorkspaceUseCase(workspace_repository)
    workspace = use_case.execute(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return to_workspace_response(workspace)


@router.post("/{workspace_id}/scan", response_model=ProjectScanResponse)
def scan_workspace_project(workspace_id: str) -> ProjectScanResponse:
    use_case = ScanWorkspaceProjectUseCase(
        workspace_repository=workspace_repository,
        file_system=file_system,
        project_scan_repository=project_scan_repository,
    )

    try:
        result = use_case.execute(ScanWorkspaceProjectInput(workspace_id=workspace_id))
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectScanError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_project_scan_response(result)


@router.get("/{workspace_id}/scan", response_model=ProjectScanResponse)
def get_workspace_latest_scan(workspace_id: str) -> ProjectScanResponse:
    use_case = GetWorkspaceLatestScanUseCase(project_scan_repository)
    result = use_case.execute(GetWorkspaceLatestScanInput(workspace_id=workspace_id))

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace scan not found",
        )

    return to_project_scan_response(result)


@router.get("/{workspace_id}/summary", response_model=WorkspaceSummaryResponse)
def get_workspace_summary(workspace_id: str) -> WorkspaceSummaryResponse:
    use_case = GetWorkspaceSummaryUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        command_repository=command_repository,
    )

    try:
        summary = use_case.execute(GetWorkspaceSummaryInput(workspace_id=workspace_id))
    except WorkspaceSummaryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_summary_response(summary)


@router.get(
    "/{workspace_id}/reports/project-overview",
    response_model=ProjectOverviewReportResponse,
)
def generate_project_overview_report(
    workspace_id: str,
) -> ProjectOverviewReportResponse:
    use_case = GenerateProjectOverviewReportUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
    )

    try:
        report = use_case.execute(
            GenerateProjectOverviewReportInput(workspace_id=workspace_id)
        )
    except ProjectOverviewReportWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectOverviewReportScanRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_project_overview_report_response(report)


@router.get(
    "/{workspace_id}/analysis/terraform",
    response_model=TerraformAnalysisResponse,
)
def analyze_workspace_terraform(workspace_id: str) -> TerraformAnalysisResponse:
    use_case = AnalyzeTerraformUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
    )

    try:
        result = use_case.execute(AnalyzeTerraformInput(workspace_id=workspace_id))
    except TerraformAnalysisWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except TerraformAnalysisScanRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_terraform_analysis_response(result)


@router.get(
    "/{workspace_id}/analysis/gitlab-ci",
    response_model=GitLabCIAnalysisResponse,
)
def analyze_workspace_gitlab_ci(workspace_id: str) -> GitLabCIAnalysisResponse:
    use_case = AnalyzeGitLabCIUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
    )

    try:
        result = use_case.execute(AnalyzeGitLabCIInput(workspace_id=workspace_id))
    except GitLabCIAnalysisWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except GitLabCIAnalysisScanRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_gitlab_ci_analysis_response(result)


@router.get(
    "/{workspace_id}/analysis/terragrunt",
    response_model=TerragruntAnalysisResponse,
)
def analyze_workspace_terragrunt(workspace_id: str) -> TerragruntAnalysisResponse:
    use_case = AnalyzeTerragruntUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
    )

    try:
        result = use_case.execute(AnalyzeTerragruntInput(workspace_id=workspace_id))
    except TerragruntAnalysisWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except TerragruntAnalysisScanRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_terragrunt_analysis_response(result)


@router.get(
    "/{workspace_id}/analysis/github-actions",
    response_model=GitHubActionsAnalysisResponse,
)
def analyze_workspace_github_actions(
    workspace_id: str,
) -> GitHubActionsAnalysisResponse:
    use_case = AnalyzeGitHubActionsUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
    )

    try:
        result = use_case.execute(AnalyzeGitHubActionsInput(workspace_id=workspace_id))
    except GitHubActionsAnalysisWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except GitHubActionsAnalysisScanRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_github_actions_analysis_response(result)


@router.get(
    "/{workspace_id}/analysis/summary",
    response_model=AnalysisSummaryResponse,
)
def get_workspace_analysis_summary(workspace_id: str) -> AnalysisSummaryResponse:
    use_case = GetAnalysisSummaryUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
    )

    try:
        result = use_case.execute(GetAnalysisSummaryInput(workspace_id=workspace_id))
    except AnalysisSummaryWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_analysis_summary_response(result)
