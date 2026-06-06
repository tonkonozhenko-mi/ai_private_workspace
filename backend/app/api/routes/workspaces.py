from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    command_repository,
    embedding_provider,
    file_system,
    index_status_repository,
    llm_provider,
    project_scan_repository,
    timeline_repository,
    vector_store,
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
from app.api.schemas.indexing_schemas import (
    ContextSearchResultResponse,
    WorkspaceIndexResponse,
    to_context_search_result_response,
    to_workspace_index_response,
)
from app.api.schemas.index_status_schemas import (
    WorkspaceIndexStatusResponse,
    to_workspace_index_status_response,
)
from app.api.schemas.report_schemas import (
    ProjectOverviewReportResponse,
    to_project_overview_report_response,
)
from app.api.schemas.rag_schemas import (
    AskWorkspaceQuestionRequest,
    WorkspaceQuestionAnswerResponse,
    to_workspace_question_answer_response,
)
from app.api.schemas.timeline_schemas import (
    TimelineBackfillResponse,
    TimelineEventResponse,
    to_timeline_backfill_response,
    to_timeline_event_response,
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
from app.core.use_cases.ask_workspace_question import (
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionNotFoundError,
    AskWorkspaceQuestionUseCase,
)
from app.core.use_cases.backfill_workspace_timeline import (
    BackfillWorkspaceTimelineInput,
    BackfillWorkspaceTimelineUseCase,
    WorkspaceTimelineBackfillNotFoundError,
)
from app.core.use_cases.create_workspace import (
    CreateWorkspaceInput,
    CreateWorkspaceUseCase,
)
from app.core.use_cases.get_workspace_latest_scan import (
    GetWorkspaceLatestScanInput,
    GetWorkspaceLatestScanUseCase,
)
from app.core.use_cases.get_workspace_index_status import (
    GetWorkspaceIndexStatusInput,
    GetWorkspaceIndexStatusUseCase,
    WorkspaceIndexStatusNotFoundError,
)
from app.core.use_cases.index_workspace import (
    IndexWorkspaceInput,
    IndexWorkspaceNotFoundError,
    IndexWorkspaceScanRequiredError,
    IndexWorkspaceUseCase,
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
from app.core.use_cases.list_workspace_timeline import (
    ListWorkspaceTimelineInput,
    ListWorkspaceTimelineUseCase,
    WorkspaceTimelineNotFoundError,
)
from app.core.use_cases.scan_project import ProjectScanError
from app.core.use_cases.scan_workspace_project import (
    ScanWorkspaceProjectInput,
    ScanWorkspaceProjectUseCase,
    WorkspaceNotFoundError,
)
from app.core.use_cases.search_workspace_context import (
    SearchWorkspaceContextInput,
    SearchWorkspaceContextNotFoundError,
    SearchWorkspaceContextUseCase,
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
    use_case = CreateWorkspaceUseCase(
        workspace_repository=workspace_repository,
        timeline_repository=timeline_repository,
    )
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
        timeline_repository=timeline_repository,
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


@router.post("/{workspace_id}/index", response_model=WorkspaceIndexResponse)
def index_workspace(workspace_id: str) -> WorkspaceIndexResponse:
    use_case = IndexWorkspaceUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        index_status_repository=index_status_repository,
        timeline_repository=timeline_repository,
    )

    try:
        result = use_case.execute(IndexWorkspaceInput(workspace_id=workspace_id))
    except IndexWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except IndexWorkspaceScanRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_workspace_index_response(result)


@router.get("/{workspace_id}/index/status", response_model=WorkspaceIndexStatusResponse)
def get_workspace_index_status(workspace_id: str) -> WorkspaceIndexStatusResponse:
    use_case = GetWorkspaceIndexStatusUseCase(
        workspace_repository=workspace_repository,
        index_status_repository=index_status_repository,
    )

    try:
        result = use_case.execute(GetWorkspaceIndexStatusInput(workspace_id=workspace_id))
    except WorkspaceIndexStatusNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_index_status_response(result)


@router.get(
    "/{workspace_id}/context/search",
    response_model=list[ContextSearchResultResponse],
)
def search_workspace_context(
    workspace_id: str,
    query: str,
    limit: int = 5,
) -> list[ContextSearchResultResponse]:
    use_case = SearchWorkspaceContextUseCase(
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    try:
        results = use_case.execute(
            SearchWorkspaceContextInput(
                workspace_id=workspace_id,
                query=query,
                limit=limit,
            )
        )
    except SearchWorkspaceContextNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [to_context_search_result_response(result) for result in results]


@router.post("/{workspace_id}/ask", response_model=WorkspaceQuestionAnswerResponse)
def ask_workspace_question(
    workspace_id: str,
    request: AskWorkspaceQuestionRequest,
) -> WorkspaceQuestionAnswerResponse:
    use_case = AskWorkspaceQuestionUseCase(
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider=llm_provider,
        index_status_repository=index_status_repository,
        timeline_repository=timeline_repository,
    )

    try:
        result = use_case.execute(
            AskWorkspaceQuestionInput(
                workspace_id=workspace_id,
                question=request.question,
                limit=request.limit,
            )
        )
    except AskWorkspaceQuestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_question_answer_response(result)


@router.get("/{workspace_id}/summary", response_model=WorkspaceSummaryResponse)
def get_workspace_summary(workspace_id: str) -> WorkspaceSummaryResponse:
    use_case = GetWorkspaceSummaryUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        command_repository=command_repository,
        index_status_repository=index_status_repository,
        timeline_repository=timeline_repository,
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
        timeline_repository=timeline_repository,
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


@router.post(
    "/{workspace_id}/timeline/backfill",
    response_model=TimelineBackfillResponse,
)
def backfill_workspace_timeline(workspace_id: str) -> TimelineBackfillResponse:
    use_case = BackfillWorkspaceTimelineUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        index_status_repository=index_status_repository,
        command_repository=command_repository,
        timeline_repository=timeline_repository,
    )

    try:
        result = use_case.execute(
            BackfillWorkspaceTimelineInput(workspace_id=workspace_id)
        )
    except WorkspaceTimelineBackfillNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_timeline_backfill_response(result)


@router.get(
    "/{workspace_id}/timeline",
    response_model=list[TimelineEventResponse],
)
def get_workspace_timeline(
    workspace_id: str,
    limit: int = 50,
) -> list[TimelineEventResponse]:
    use_case = ListWorkspaceTimelineUseCase(
        workspace_repository=workspace_repository,
        timeline_repository=timeline_repository,
    )

    try:
        events = use_case.execute(
            ListWorkspaceTimelineInput(
                workspace_id=workspace_id,
                limit=limit,
            )
        )
    except WorkspaceTimelineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [to_timeline_event_response(event) for event in events]


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
