import json
import logging
from dataclasses import replace
from datetime import datetime

from fastapi import APIRouter, Body, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.dependencies import (
    project_context_composer,
    build_active_model_configuration,
    build_reranker,
    command_repository,
    conversation_repository,
    embedding_provider,
    file_system,
    git_history,
    index_status_repository,
    indexing_rules_repository,
    llm_provider_factory,
    model_catalog_registry,
    model_experiment_rating_repository,
    model_experiment_repository,
    project_scan_repository,
    project_understanding_repository,
    readiness_configuration,
    report_repository,
    runtime_health_checkers,
    runtime_health_configuration,
    skill_profile_repository,
    timeline_repository,
    vector_store,
    workspace_job_runner,
    workspace_model_selection_repository,
    workspace_repository,
    workspace_storage_gateway,
)

logger = logging.getLogger("uvicorn.error.ai_private_workspace.workspace_api")
from app.api.project_scan_schemas import (
    FileSelectionPreviewResponse,
    ProjectScanResponse,
    ScanChangesResponse,
    ScanWorkspaceProjectRequest,
    to_file_selection_preview_response,
    to_project_scan_response,
    to_scan_changes_response,
)
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
from app.api.schemas.conversation_schemas import (
    AnswerNotePinRequest,
    ConversationAnswerNoteResponse,
    ConversationArchiveRequest,
    ConversationContextPreviewResponse,
    ConversationExportResponse,
    ConversationPinRequest,
    CreateConversationRequest,
    SaveAnswerNoteRequest,
    UpdateAnswerNoteRequest,
    UpdateConversationRequest,
    WorkspaceConversationResponse,
    to_answer_note_response,
    to_workspace_conversation_response,
)
from app.api.schemas.git_insights_schemas import (
    GitInsightsResponse,
    to_git_insights_response,
)
from app.api.schemas.guided_model_setup_schemas import (
    GuidedModelSetupGuideResponse,
    to_guided_model_setup_guide_response,
)
from app.api.schemas.index_status_schemas import (
    WorkspaceIndexStatusResponse,
    to_workspace_index_status_response,
)
from app.api.schemas.indexing_rules_schemas import (
    WorkspaceIndexingRulesRequest,
    WorkspaceIndexingRulesResponse,
    to_workspace_indexing_rules_response,
)
from app.api.schemas.indexing_schemas import (
    ContextSearchResultResponse,
    WorkspaceIndexResponse,
    to_context_search_result_response,
    to_workspace_index_response,
)
from app.api.schemas.local_ai_activation_guide_schemas import (
    LocalAIActivationGuideResponse,
    to_local_ai_activation_guide_response,
)
from app.api.schemas.model_experiment_run_schemas import (
    ModelExperimentRunResponse,
    to_model_experiment_run_response,
)
from app.api.schemas.model_performance_schemas import (
    ModelPerformanceSummaryResponse,
    to_model_performance_summary_response,
)
from app.api.schemas.model_recommendation_explanation_schemas import (
    ExplainWorkspaceModelRecommendationRequest,
    ModelRecommendationExplanationResponse,
    to_model_recommendation_explanation_response,
)
from app.api.schemas.project_todos_schemas import (
    ProjectTodosResponse,
    to_project_todos_response,
)
from app.api.schemas.project_understanding_schemas import (
    ProjectUnderstandingResponse,
    to_project_understanding_response,
)
from app.api.schemas.rag_schemas import (
    AskWorkspaceQuestionRequest,
    AskWorkspaceQuestionWithSelectedLLMRequest,
    WorkspaceQuestionAnswerResponse,
    to_workspace_question_answer_response,
)
from app.api.schemas.report_schemas import (
    BuildCustomWorkspaceReportRequest,
    ProjectOverviewReportResponse,
    ReportCatalogResponse,
    SaveCustomWorkspaceReportRequest,
    SavedReportPinRequest,
    SavedWorkspaceReportResponse,
    SaveEditedWorkspaceReportRequest,
    UpdateSavedWorkspaceReportRequest,
    to_project_overview_report_response,
    to_report_catalog_response,
    to_saved_workspace_report_response,
)
from app.api.schemas.selected_embedding_indexing_plan_schemas import (
    SelectedEmbeddingIndexingPlanResponse,
    to_selected_embedding_indexing_plan_response,
)
from app.api.schemas.selected_model_usage_plan_schemas import (
    SelectedModelUsagePlanResponse,
    to_selected_model_usage_plan_response,
)
from app.api.schemas.skill_profile_schemas import (
    WorkspaceSkillProfileRequest,
    WorkspaceSkillProfileResponse,
    to_skill_profile_item,
    to_workspace_skill_profile_response,
)
from app.api.schemas.timeline_schemas import (
    TimelineBackfillResponse,
    TimelineEventResponse,
    to_timeline_backfill_response,
    to_timeline_event_response,
)
from app.api.schemas.workspace_dashboard_schemas import (
    WorkspaceDashboardResponse,
    to_workspace_dashboard_response,
)
from app.api.schemas.workspace_file_schemas import (
    WorkspaceFileWriteResponse,
    WriteWorkspaceFileRequest,
    to_workspace_file_write_response,
)
from app.api.schemas.workspace_job_schemas import WorkspaceJobResponse
from app.api.schemas.workspace_model_recommendation_schemas import (
    RecommendWorkspaceModelsRequest,
    WorkspaceModelRecommendationResultResponse,
    to_workspace_model_recommendation_result_response,
)
from app.api.schemas.workspace_model_selection_schemas import (
    UpdateWorkspaceModelSelectionRequest,
    WorkspaceModelSelectionResponse,
    to_workspace_model_selection_response,
)
from app.api.schemas.workspace_model_selection_status_schemas import (
    WorkspaceModelSelectionStatusResponse,
    to_workspace_model_selection_status_response,
)
from app.api.schemas.workspace_models_dashboard_schemas import (
    WorkspaceModelsDashboardResponse,
    to_workspace_models_dashboard_response,
)
from app.api.schemas.workspace_models_dashboard_summary_schemas import (
    WorkspaceModelsDashboardSummaryResponse,
    to_workspace_models_dashboard_summary_response,
)
from app.api.schemas.workspace_quick_start_schemas import (
    WorkspaceQuickStartResponse,
    to_workspace_quick_start_response,
)
from app.api.schemas.workspace_readiness_schemas import (
    WorkspaceReadinessResponse,
    to_workspace_readiness_response,
)
from app.api.schemas.workspace_storage_schemas import (
    WorkspaceStorageResponse,
    to_workspace_storage_response,
)
from app.api.schemas.workspace_summary_schemas import (
    WorkspaceSummaryResponse,
    to_workspace_summary_response,
)
from app.api.schemas.workspace_ui_actions_schemas import (
    WorkspaceUIActionCatalogResponse,
    to_workspace_ui_action_catalog_response,
)
from app.api.schemas.workspaces_overview_schemas import (
    WorkspacesOverviewResponse,
    to_workspaces_overview_response,
)
from app.api.workspace_job_runner import (
    WorkspaceJob,
    WorkspaceJobCancelledError,
    WorkspaceJobNotFoundError,
)
from app.core.domain.attached_documents import AttachedDocument
from app.core.domain.conversation import (
    create_conversation_answer_note,
    create_conversation_message,
    create_workspace_conversation,
)
from app.core.domain.indexing_rules import IndexingRulesProfile, default_indexing_rules
from app.core.domain.rag_prompt import SkillPromptInstruction
from app.core.domain.report import (
    ProjectOverviewReport,
    ReportSection,
    create_saved_workspace_report,
    create_saved_workspace_report_from_draft,
    markdown_to_plain_text,
    render_report_markdown,
)
from app.core.domain.skill_profile import default_skill_profile, normalize_skill_profile
from app.core.domain.workspace import Workspace
from app.core.use_cases.add_timeline_event import AddTimelineEventInput, AddTimelineEventUseCase
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
from app.core.use_cases.archive_workspace import (
    ArchiveWorkspaceInput,
    ArchiveWorkspaceNotFoundError,
    ArchiveWorkspaceUseCase,
)
from app.core.use_cases.ask_workspace_question import (
    AskStreamDelta,
    AskStreamFinal,
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionNotFoundError,
    AskWorkspaceQuestionUseCase,
    AskWorkspaceQuestionValidationError,
)
from app.core.use_cases.ask_workspace_question_with_selected_llm import (
    AskWorkspaceQuestionWithSelectedLLMInput,
    AskWorkspaceQuestionWithSelectedLLMNotFoundError,
    AskWorkspaceQuestionWithSelectedLLMUseCase,
    AskWorkspaceQuestionWithSelectedLLMValidationError,
)
from app.core.use_cases.backfill_workspace_timeline import (
    BackfillWorkspaceTimelineInput,
    BackfillWorkspaceTimelineUseCase,
    WorkspaceTimelineBackfillNotFoundError,
)
from app.core.use_cases.clear_workspace_index import (
    ClearWorkspaceIndexInput,
    ClearWorkspaceIndexNotFoundError,
    ClearWorkspaceIndexUseCase,
)
from app.core.use_cases.create_workspace import (
    CreateWorkspaceInput,
    CreateWorkspaceUseCase,
)
from app.core.use_cases.delete_workspace import (
    DeleteWorkspaceInput,
    DeleteWorkspaceNotFoundError,
    DeleteWorkspaceUseCase,
)
from app.core.use_cases.explain_workspace_model_recommendation import (
    ExplainWorkspaceModelRecommendationInput,
    ExplainWorkspaceModelRecommendationUseCase,
    ModelRecommendationExplanationNotFoundError,
)
from app.core.use_cases.generate_project_overview_report import (
    GenerateProjectOverviewReportInput,
    GenerateProjectOverviewReportUseCase,
    ProjectOverviewReportScanRequiredError,
    ProjectOverviewReportWorkspaceNotFoundError,
)
from app.core.use_cases.generate_project_understanding import (
    GenerateProjectUnderstandingInput,
    GenerateProjectUnderstandingNotFoundError,
    GenerateProjectUnderstandingUseCase,
    GenerateProjectUnderstandingValidationError,
)
from app.core.use_cases.generate_workspace_report import (
    GenerateWorkspaceReportInput,
    GenerateWorkspaceReportUseCase,
    GetWorkspaceReportCatalogInput,
    GetWorkspaceReportCatalogUseCase,
    WorkspaceReportNotFoundError,
    WorkspaceReportScanRequiredError,
    WorkspaceReportTypeNotFoundError,
)
from app.core.use_cases.get_analysis_summary import (
    AnalysisSummaryWorkspaceNotFoundError,
    GetAnalysisSummaryInput,
    GetAnalysisSummaryUseCase,
)
from app.core.use_cases.get_guided_model_setup import (
    GetGuidedModelSetupInput,
    GetGuidedModelSetupUseCase,
    GuidedModelSetupNotFoundError,
)
from app.core.use_cases.get_local_ai_activation_guide import (
    GetLocalAIActivationGuideInput,
    GetLocalAIActivationGuideUseCase,
    LocalAIActivationGuideNotFoundError,
)
from app.core.use_cases.get_model_performance_summary import (
    GetModelPerformanceSummaryInput,
    GetModelPerformanceSummaryUseCase,
    ModelPerformanceWorkspaceNotFoundError,
)
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase
from app.core.use_cases.get_selected_embedding_indexing_plan import (
    GetSelectedEmbeddingIndexingPlanInput,
    GetSelectedEmbeddingIndexingPlanUseCase,
    SelectedEmbeddingIndexingPlanNotFoundError,
)
from app.core.use_cases.get_selected_model_usage_plan import (
    GetSelectedModelUsagePlanInput,
    GetSelectedModelUsagePlanUseCase,
    SelectedModelUsagePlanNotFoundError,
)
from app.core.use_cases.get_workspace import GetWorkspaceUseCase
from app.core.use_cases.get_workspace_assistant_recommendation import (
    GetWorkspaceAssistantRecommendationUseCase,
)
from app.core.use_cases.get_workspace_dashboard import (
    GetWorkspaceDashboardInput,
    GetWorkspaceDashboardUseCase,
    WorkspaceDashboardNotFoundError,
)
from app.core.use_cases.get_workspace_git_insights import (
    GetWorkspaceGitInsightsInput,
    GetWorkspaceGitInsightsUseCase,
    WorkspaceGitInsightsNotFoundError,
)
from app.core.use_cases.get_workspace_index_status import (
    GetWorkspaceIndexStatusInput,
    GetWorkspaceIndexStatusUseCase,
    WorkspaceIndexStatusNotFoundError,
)
from app.core.use_cases.get_workspace_indexing_rules import (
    GetWorkspaceIndexingRulesInput,
    GetWorkspaceIndexingRulesNotFoundError,
    GetWorkspaceIndexingRulesUseCase,
)
from app.core.use_cases.get_workspace_latest_scan import (
    GetWorkspaceLatestScanInput,
    GetWorkspaceLatestScanUseCase,
)
from app.core.use_cases.get_workspace_model_selection import (
    GetWorkspaceModelSelectionInput,
    GetWorkspaceModelSelectionUseCase,
    WorkspaceModelSelectionNotFoundError,
)
from app.core.use_cases.get_workspace_model_selection_status import (
    GetWorkspaceModelSelectionStatusInput,
    GetWorkspaceModelSelectionStatusUseCase,
    WorkspaceModelSelectionStatusNotFoundError,
)
from app.core.use_cases.get_workspace_models_dashboard import (
    GetWorkspaceModelsDashboardInput,
    GetWorkspaceModelsDashboardUseCase,
    WorkspaceModelsDashboardNotFoundError,
)
from app.core.use_cases.get_workspace_models_dashboard_summary import (
    GetWorkspaceModelsDashboardSummaryInput,
    GetWorkspaceModelsDashboardSummaryUseCase,
    WorkspaceModelsDashboardSummaryNotFoundError,
)
from app.core.use_cases.get_workspace_quick_start import (
    GetWorkspaceQuickStartInput,
    GetWorkspaceQuickStartUseCase,
    WorkspaceQuickStartNotFoundError,
)
from app.core.use_cases.get_workspace_readiness import (
    GetWorkspaceReadinessInput,
    GetWorkspaceReadinessUseCase,
    WorkspaceReadinessNotFoundError,
)
from app.core.use_cases.get_workspace_scan_changes import (
    GetWorkspaceScanChangesInput,
    GetWorkspaceScanChangesUseCase,
    WorkspaceScanChangesWorkspaceNotFoundError,
)
from app.core.use_cases.get_workspace_storage import (
    GetWorkspaceStorageInput,
    GetWorkspaceStorageNotFoundError,
    GetWorkspaceStorageUseCase,
)
from app.core.use_cases.get_workspace_summary import (
    GetWorkspaceSummaryInput,
    GetWorkspaceSummaryUseCase,
    WorkspaceSummaryNotFoundError,
)
from app.core.use_cases.get_workspace_todos import (
    GetWorkspaceTodosInput,
    GetWorkspaceTodosUseCase,
    WorkspaceTodosNotFoundError,
)
from app.core.use_cases.get_workspace_ui_actions import (
    GetWorkspaceUIActionsInput,
    GetWorkspaceUIActionsUseCase,
    WorkspaceUIActionsNotFoundError,
)
from app.core.use_cases.index_workspace import (
    IndexWorkspaceCancelledError,
    IndexWorkspaceInput,
    IndexWorkspaceNotFoundError,
    IndexWorkspaceScanRequiredError,
    IndexWorkspaceUseCase,
)
from app.core.use_cases.list_workspace_model_experiments import (
    ListWorkspaceModelExperimentsInput,
    ListWorkspaceModelExperimentsUseCase,
    WorkspaceModelExperimentsNotFoundError,
)
from app.core.use_cases.list_workspace_timeline import (
    ListWorkspaceTimelineInput,
    ListWorkspaceTimelineUseCase,
    WorkspaceTimelineNotFoundError,
)
from app.core.use_cases.list_workspaces import ListWorkspacesUseCase
from app.core.use_cases.list_workspaces_overview import ListWorkspacesOverviewUseCase
from app.core.use_cases.manage_saved_workspace_reports import (
    DeleteSavedWorkspaceReportInput,
    DeleteSavedWorkspaceReportUseCase,
    GetSavedWorkspaceReportInput,
    GetSavedWorkspaceReportUseCase,
    ListSavedWorkspaceReportsInput,
    ListSavedWorkspaceReportsUseCase,
    SavedWorkspaceReportNotFoundError,
    UpdateSavedWorkspaceReportInput,
    UpdateSavedWorkspaceReportUseCase,
)
from app.core.use_cases.preview_workspace_file_selection import (
    PreviewWorkspaceFileSelectionError,
    PreviewWorkspaceFileSelectionInput,
    PreviewWorkspaceFileSelectionUseCase,
    PreviewWorkspaceFileSelectionWorkspaceNotFoundError,
)
from app.core.use_cases.purge_temporary_workspaces import (
    PurgeTemporaryWorkspacesUseCase,
)
from app.core.use_cases.recommend_models import ModelRecommendationValidationError
from app.core.use_cases.recommend_workspace_models import (
    RecommendWorkspaceModelsInput,
    RecommendWorkspaceModelsUseCase,
    WorkspaceModelRecommendationNotFoundError,
)
from app.core.use_cases.restore_workspace import (
    RestoreWorkspaceInput,
    RestoreWorkspaceNotFoundError,
    RestoreWorkspaceUseCase,
)
from app.core.use_cases.save_workspace_report import (
    SaveWorkspaceReportInput,
    SaveWorkspaceReportUseCase,
)
from app.core.use_cases.scan_project import (
    ProjectScanCancelledError,
    ProjectScanError,
    ScanProjectUseCase,
)
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
from app.core.use_cases.set_workspace_persistence import (
    SetWorkspacePersistenceInput,
    SetWorkspacePersistenceNotFoundError,
    SetWorkspacePersistenceUseCase,
    SetWorkspacePersistenceValidationError,
)
from app.core.use_cases.update_workspace_indexing_rules import (
    UpdateWorkspaceIndexingRulesInput,
    UpdateWorkspaceIndexingRulesNotFoundError,
    UpdateWorkspaceIndexingRulesUseCase,
    UpdateWorkspaceIndexingRulesValidationError,
)
from app.core.use_cases.update_workspace_metadata import (
    UpdateWorkspaceMetadataInput,
    UpdateWorkspaceMetadataNotFoundError,
    UpdateWorkspaceMetadataUseCase,
    UpdateWorkspaceMetadataValidationError,
)
from app.core.use_cases.update_workspace_model_selection import (
    UpdateWorkspaceModelSelectionInput,
    UpdateWorkspaceModelSelectionNotFoundError,
    UpdateWorkspaceModelSelectionUseCase,
    UpdateWorkspaceModelSelectionValidationError,
)
from app.core.use_cases.write_workspace_file import (
    WriteWorkspaceFileInput,
    WriteWorkspaceFileNotFoundError,
    WriteWorkspaceFileUseCase,
    WriteWorkspaceFileValidationError,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _safe_invalidate_storage(workspace_id: str) -> None:
    """Drop the cached storage size so the next read recomputes it.

    Storage stats are best-effort: never let a cache refresh failure break the
    surrounding scan/index request.
    """
    try:
        workspace_storage_gateway.invalidate(workspace_id)
    except Exception:  # noqa: BLE001
        logger.warning("Could not invalidate storage stats for %s", workspace_id)


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1)
    project_path: str = Field(..., min_length=1)
    assistant_mode: str = Field(default="local")
    privacy_mode: str = Field(default="private")
    persistence: str = Field(default="saved")


class SetWorkspacePersistenceRequest(BaseModel):
    persistence: str = Field(default="saved")


class UpdateWorkspaceMetadataRequest(BaseModel):
    name: str | None = None
    assistant_mode: str | None = None
    privacy_mode: str | None = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: datetime
    archived_at: str | None
    persistence: str = "saved"


class PurgeTemporaryWorkspacesResponse(BaseModel):
    deleted_count: int
    deleted_ids: list[str]


def to_workspace_response(workspace: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        project_path=workspace.project_path,
        assistant_mode=workspace.assistant_mode,
        privacy_mode=workspace.privacy_mode,
        created_at=workspace.created_at,
        archived_at=workspace.archived_at,
        persistence=workspace.persistence,
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
            persistence=request.persistence,
        )
    )
    return to_workspace_response(workspace)


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces() -> list[WorkspaceResponse]:
    use_case = ListWorkspacesUseCase(workspace_repository)
    return [to_workspace_response(workspace) for workspace in use_case.execute()]


@router.get("/overview", response_model=WorkspacesOverviewResponse)
def list_workspaces_overview(
    include_archived: bool = False,
) -> WorkspacesOverviewResponse:
    overview = ListWorkspacesOverviewUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        index_status_repository=index_status_repository,
        command_repository=command_repository,
        timeline_repository=timeline_repository,
        configuration=readiness_configuration,
        storage_gateway=workspace_storage_gateway,
        selection_repository=workspace_model_selection_repository,
    ).execute(include_archived=include_archived)
    return to_workspaces_overview_response(overview)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: str) -> WorkspaceResponse:
    use_case = GetWorkspaceUseCase(workspace_repository)
    workspace = use_case.execute(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return to_workspace_response(workspace)


@router.get("/{workspace_id}/indexing-rules", response_model=WorkspaceIndexingRulesResponse)
def get_workspace_indexing_rules(workspace_id: str) -> WorkspaceIndexingRulesResponse:
    try:
        profile = GetWorkspaceIndexingRulesUseCase(
            workspace_repository=workspace_repository,
            indexing_rules_repository=indexing_rules_repository,
        ).execute(GetWorkspaceIndexingRulesInput(workspace_id=workspace_id))
    except GetWorkspaceIndexingRulesNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    source = "saved" if indexing_rules_repository.get(workspace_id) is not None else "default"
    return to_workspace_indexing_rules_response(profile, source=source)


@router.post(
    "/{workspace_id}/files/write",
    response_model=WorkspaceFileWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
def write_workspace_file(
    workspace_id: str,
    request: WriteWorkspaceFileRequest,
) -> WorkspaceFileWriteResponse:
    try:
        result = WriteWorkspaceFileUseCase(
            workspace_repository=workspace_repository,
            file_system=file_system,
            timeline_repository=timeline_repository,
        ).execute(
            WriteWorkspaceFileInput(
                workspace_id=workspace_id,
                relative_path=request.relative_path,
                content=request.content,
                overwrite=request.overwrite,
            )
        )
    except WriteWorkspaceFileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WriteWorkspaceFileValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_workspace_file_write_response(result)


@router.put("/{workspace_id}/indexing-rules", response_model=WorkspaceIndexingRulesResponse)
def update_workspace_indexing_rules(
    workspace_id: str,
    request: WorkspaceIndexingRulesRequest,
) -> WorkspaceIndexingRulesResponse:
    try:
        profile = UpdateWorkspaceIndexingRulesUseCase(
            workspace_repository=workspace_repository,
            indexing_rules_repository=indexing_rules_repository,
            timeline_repository=timeline_repository,
        ).execute(
            UpdateWorkspaceIndexingRulesInput(
                workspace_id=workspace_id,
                profile=request.profile,
                include_patterns=tuple(request.include_patterns),
                exclude_patterns=tuple(request.exclude_patterns),
            )
        )
    except UpdateWorkspaceIndexingRulesNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UpdateWorkspaceIndexingRulesValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_workspace_indexing_rules_response(profile, source="saved")


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace_metadata(
    workspace_id: str,
    request: UpdateWorkspaceMetadataRequest,
) -> WorkspaceResponse:
    try:
        workspace = UpdateWorkspaceMetadataUseCase(
            workspace_repository=workspace_repository,
            timeline_repository=timeline_repository,
        ).execute(
            UpdateWorkspaceMetadataInput(
                workspace_id=workspace_id,
                name=request.name,
                assistant_mode=request.assistant_mode,
                privacy_mode=request.privacy_mode,
            )
        )
    except UpdateWorkspaceMetadataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UpdateWorkspaceMetadataValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_workspace_response(workspace)


@router.post("/{workspace_id}/archive", response_model=WorkspaceResponse)
def archive_workspace(workspace_id: str) -> WorkspaceResponse:
    try:
        workspace = ArchiveWorkspaceUseCase(
            workspace_repository=workspace_repository,
            timeline_repository=timeline_repository,
        ).execute(ArchiveWorkspaceInput(workspace_id=workspace_id))
    except ArchiveWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_workspace_response(workspace)


@router.get("/{workspace_id}/storage", response_model=WorkspaceStorageResponse)
def get_workspace_storage(
    workspace_id: str,
    recompute: bool = False,
) -> WorkspaceStorageResponse:
    try:
        breakdown = GetWorkspaceStorageUseCase(
            workspace_repository=workspace_repository,
            storage_gateway=workspace_storage_gateway,
        ).execute(GetWorkspaceStorageInput(workspace_id=workspace_id, recompute=recompute))
    except GetWorkspaceStorageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_workspace_storage_response(breakdown)


@router.post("/{workspace_id}/index/clear", response_model=WorkspaceStorageResponse)
def clear_workspace_index(workspace_id: str) -> WorkspaceStorageResponse:
    try:
        breakdown = ClearWorkspaceIndexUseCase(
            workspace_repository=workspace_repository,
            vector_store=vector_store,
            index_status_repository=index_status_repository,
            storage_gateway=workspace_storage_gateway,
            timeline_repository=timeline_repository,
        ).execute(ClearWorkspaceIndexInput(workspace_id=workspace_id))
    except ClearWorkspaceIndexNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_workspace_storage_response(breakdown)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: str) -> None:
    try:
        DeleteWorkspaceUseCase(
            workspace_repository=workspace_repository,
            storage_gateway=workspace_storage_gateway,
            vector_store=vector_store,
        ).execute(DeleteWorkspaceInput(workspace_id=workspace_id))
    except DeleteWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return None


@router.post("/temporary/purge", response_model=PurgeTemporaryWorkspacesResponse)
def purge_temporary_workspaces() -> PurgeTemporaryWorkspacesResponse:
    result = PurgeTemporaryWorkspacesUseCase(
        workspace_repository=workspace_repository,
        storage_gateway=workspace_storage_gateway,
        vector_store=vector_store,
    ).execute()
    return PurgeTemporaryWorkspacesResponse(
        deleted_count=result.deleted_count,
        deleted_ids=result.deleted_ids,
    )


@router.post("/{workspace_id}/persistence", response_model=WorkspaceResponse)
def set_workspace_persistence(
    workspace_id: str,
    request: SetWorkspacePersistenceRequest,
) -> WorkspaceResponse:
    try:
        workspace = SetWorkspacePersistenceUseCase(
            workspace_repository=workspace_repository,
            timeline_repository=timeline_repository,
        ).execute(
            SetWorkspacePersistenceInput(
                workspace_id=workspace_id,
                persistence=request.persistence,
            )
        )
    except SetWorkspacePersistenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SetWorkspacePersistenceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_workspace_response(workspace)


@router.post("/{workspace_id}/restore", response_model=WorkspaceResponse)
def restore_workspace(workspace_id: str) -> WorkspaceResponse:
    try:
        workspace = RestoreWorkspaceUseCase(
            workspace_repository=workspace_repository,
            timeline_repository=timeline_repository,
        ).execute(RestoreWorkspaceInput(workspace_id=workspace_id))
    except RestoreWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_workspace_response(workspace)


def _to_workspace_job_response(job: WorkspaceJob) -> WorkspaceJobResponse:
    return WorkspaceJobResponse(
        job_id=job.job_id,
        workspace_id=job.workspace_id,
        job_type=job.job_type,
        status=job.status,
        title=job.title,
        message=job.message,
        result_summary=job.result_summary,
        request_summary=job.request_summary,
        error=job.error,
        cancellation_requested=job.cancellation_requested,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_ms=job.duration_ms,
    )


def _scan_workspace_result_summary(result) -> dict[str, str]:
    return {
        "total_files": str(result.total_files),
        "scanned_files": str(result.scanned_files),
        "skipped_files": str(result.skipped_files),
        "detected_skills_count": str(len(result.detected_skills)),
    }


def _file_rules_request_summary(
    *,
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
    file_rules_profile: str | None,
) -> dict[str, str]:
    return {
        "file_rules_profile": file_rules_profile or "balanced",
        "include_rules_count": str(len(include_patterns)),
        "exclude_rules_count": str(len(exclude_patterns)),
        "include_patterns": _join_patterns(include_patterns) or "All files",
        "exclude_patterns": _join_patterns(exclude_patterns) or "No exclusions",
    }


def _join_patterns(patterns: tuple[str, ...]) -> str:
    return " · ".join(pattern for pattern in patterns if pattern.strip())


def _resolve_file_rules(
    workspace_id: str, request: ScanWorkspaceProjectRequest | None
) -> IndexingRulesProfile:
    if request is not None and request.file_rules is not None:
        file_rules = request.file_rules
        return IndexingRulesProfile(
            workspace_id=workspace_id,
            profile=file_rules.profile,
            include_patterns=tuple(file_rules.include_patterns),
            exclude_patterns=tuple(file_rules.exclude_patterns),
            updated_at=None,
        )
    return indexing_rules_repository.get(workspace_id) or default_indexing_rules(workspace_id)


def _index_workspace_result_summary(result) -> dict[str, str]:
    return {
        "indexed_files_count": str(result.indexed_files_count),
        "chunks_count": str(result.chunks_count),
        "skipped_files_count": str(result.skipped_files_count),
    }


@router.post("/{workspace_id}/files/preview", response_model=FileSelectionPreviewResponse)
def preview_workspace_file_selection(
    workspace_id: str,
    request: ScanWorkspaceProjectRequest | None = Body(default=None),
) -> FileSelectionPreviewResponse:
    resolved_rules = _resolve_file_rules(workspace_id, request)
    use_case = PreviewWorkspaceFileSelectionUseCase(
        workspace_repository=workspace_repository,
        file_system=file_system,
    )

    try:
        result = use_case.execute(
            PreviewWorkspaceFileSelectionInput(
                workspace_id=workspace_id,
                include_patterns=resolved_rules.include_patterns,
                exclude_patterns=resolved_rules.exclude_patterns,
                file_rules_profile=resolved_rules.profile,
            )
        )
    except PreviewWorkspaceFileSelectionWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PreviewWorkspaceFileSelectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_file_selection_preview_response(result)


@router.post("/{workspace_id}/jobs/scan", response_model=WorkspaceJobResponse)
def start_scan_workspace_job(
    workspace_id: str,
    request: ScanWorkspaceProjectRequest | None = Body(default=None),
) -> WorkspaceJobResponse:
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    resolved_rules = _resolve_file_rules(workspace_id, request)
    include_patterns = resolved_rules.include_patterns
    exclude_patterns = resolved_rules.exclude_patterns
    file_rules_profile = resolved_rules.profile

    def operation(job_control) -> dict[str, str]:
        job_control.update_progress(
            message="Preparing project scan...",
            current_step="prepare",
        )
        try:
            result = ScanWorkspaceProjectUseCase(
                workspace_repository=workspace_repository,
                file_system=file_system,
                project_scan_repository=project_scan_repository,
                timeline_repository=timeline_repository,
            ).execute(
                ScanWorkspaceProjectInput(
                    workspace_id=workspace_id,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                    file_rules_profile=file_rules_profile,
                    cancellation_check=job_control.is_cancellation_requested,
                    progress_callback=lambda current, total, message: job_control.update_progress(
                        current=current,
                        total=total,
                        message=message,
                        current_step="scan",
                    ),
                )
            )
        except ProjectScanCancelledError as exc:
            raise WorkspaceJobCancelledError(str(exc)) from exc
        job_control.checkpoint("Finalizing project scan...")
        return _scan_workspace_result_summary(result)

    job = workspace_job_runner.start_job(
        workspace_id=workspace_id,
        job_type="scan",
        title="Scan project",
        message="Queued project scan.",
        operation=operation,
        request_summary=_file_rules_request_summary(
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            file_rules_profile=file_rules_profile,
        ),
    )
    return _to_workspace_job_response(job)


@router.post("/{workspace_id}/jobs/index", response_model=WorkspaceJobResponse)
def start_index_workspace_job(workspace_id: str) -> WorkspaceJobResponse:
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    resolved_rules = _resolve_file_rules(workspace_id, None)

    def operation(job_control) -> dict[str, str]:
        job_control.update_progress(
            message="Preparing search context build...",
            current_step="prepare",
        )
        try:
            result = IndexWorkspaceUseCase(
                workspace_repository=workspace_repository,
                project_scan_repository=project_scan_repository,
                file_system=file_system,
                embedding_provider=embedding_provider,
                vector_store=vector_store,
                index_status_repository=index_status_repository,
                timeline_repository=timeline_repository,
            ).execute(
                IndexWorkspaceInput(
                    workspace_id=workspace_id,
                    cancellation_check=job_control.is_cancellation_requested,
                    progress_callback=lambda current, total, message: job_control.update_progress(
                        current=current,
                        total=total,
                        message=message,
                        current_step="index",
                    ),
                )
            )
        except IndexWorkspaceCancelledError as exc:
            raise WorkspaceJobCancelledError(str(exc)) from exc
        job_control.checkpoint("Finalizing search context build...")
        _safe_invalidate_storage(workspace_id)
        return _index_workspace_result_summary(result)

    job = workspace_job_runner.start_job(
        workspace_id=workspace_id,
        job_type="index",
        title="Build search context",
        message="Queued search context build.",
        operation=operation,
        request_summary={
            **_file_rules_request_summary(
                include_patterns=resolved_rules.include_patterns,
                exclude_patterns=resolved_rules.exclude_patterns,
                file_rules_profile=resolved_rules.profile,
            ),
            "source": "latest_scan",
            "rules_source": "saved workspace rules",
        },
    )
    return _to_workspace_job_response(job)


@router.get("/{workspace_id}/jobs", response_model=list[WorkspaceJobResponse])
def list_workspace_jobs(workspace_id: str) -> list[WorkspaceJobResponse]:
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return [
        _to_workspace_job_response(job)
        for job in workspace_job_runner.list_workspace_jobs(workspace_id)
    ]


@router.get("/{workspace_id}/jobs/{job_id}", response_model=WorkspaceJobResponse)
def get_workspace_job(workspace_id: str, job_id: str) -> WorkspaceJobResponse:
    try:
        job = workspace_job_runner.get_job(job_id)
    except WorkspaceJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace job not found",
        ) from exc
    if job.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace job not found",
        )
    return _to_workspace_job_response(job)


@router.post("/{workspace_id}/jobs/{job_id}/cancel", response_model=WorkspaceJobResponse)
def cancel_workspace_job(workspace_id: str, job_id: str) -> WorkspaceJobResponse:
    try:
        job = workspace_job_runner.get_job(job_id)
    except WorkspaceJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace job not found",
        ) from exc
    if job.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace job not found",
        )
    return _to_workspace_job_response(workspace_job_runner.cancel_job(job_id))


@router.post("/{workspace_id}/scan", response_model=ProjectScanResponse)
def scan_workspace_project(
    workspace_id: str,
    request: ScanWorkspaceProjectRequest | None = Body(default=None),
) -> ProjectScanResponse:
    use_case = ScanWorkspaceProjectUseCase(
        workspace_repository=workspace_repository,
        file_system=file_system,
        project_scan_repository=project_scan_repository,
        timeline_repository=timeline_repository,
    )

    try:
        resolved_rules = _resolve_file_rules(workspace_id, request)
        result = use_case.execute(
            ScanWorkspaceProjectInput(
                workspace_id=workspace_id,
                include_patterns=resolved_rules.include_patterns,
                exclude_patterns=resolved_rules.exclude_patterns,
                file_rules_profile=resolved_rules.profile,
            )
        )
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

    _safe_invalidate_storage(workspace_id)
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


@router.get("/{workspace_id}/scan/changes", response_model=ScanChangesResponse)
def get_workspace_scan_changes(workspace_id: str) -> ScanChangesResponse:
    resolved_rules = _resolve_file_rules(workspace_id, None)
    use_case = GetWorkspaceScanChangesUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
    )

    try:
        result = use_case.execute(
            GetWorkspaceScanChangesInput(
                workspace_id=workspace_id,
                include_patterns=resolved_rules.include_patterns,
                exclude_patterns=resolved_rules.exclude_patterns,
            )
        )
    except WorkspaceScanChangesWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_scan_changes_response(result)


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

    _safe_invalidate_storage(workspace_id)
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


@router.get("/{workspace_id}/skill-profile", response_model=WorkspaceSkillProfileResponse)
def get_workspace_skill_profile(workspace_id: str) -> WorkspaceSkillProfileResponse:
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace not found: {workspace_id}",
        )
    saved = skill_profile_repository.get(workspace_id)
    if saved is None:
        return to_workspace_skill_profile_response(
            default_skill_profile(workspace_id),
            source="default",
        )
    return to_workspace_skill_profile_response(saved, source="saved")


@router.put("/{workspace_id}/skill-profile", response_model=WorkspaceSkillProfileResponse)
def update_workspace_skill_profile(
    workspace_id: str,
    request: WorkspaceSkillProfileRequest,
) -> WorkspaceSkillProfileResponse:
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace not found: {workspace_id}",
        )
    profile = normalize_skill_profile(
        workspace_id=workspace_id,
        profile=request.profile,
        skills=[to_skill_profile_item(item) for item in request.skills],
    )
    saved = skill_profile_repository.save(profile)
    enabled_skill_names = [skill.name for skill in saved.enabled_skills]
    AddTimelineEventUseCase(timeline_repository).execute(
        AddTimelineEventInput(
            workspace_id=workspace_id,
            event_type="skill_profile_saved",
            title="Skill profile saved",
            summary=(
                "Saved workspace skill profile with "
                f"{saved.enabled_skills_count} active skill"
                f"{'s' if saved.enabled_skills_count != 1 else ''}."
            ),
            metadata={
                "profile": saved.profile,
                "enabled_skills_count": str(saved.enabled_skills_count),
                "enabled_skills": ", ".join(enabled_skill_names) or "none",
                "source": "saved",
            },
        )
    )
    return to_workspace_skill_profile_response(saved, source="saved")


def _saved_skill_profile_context(workspace_id: str):
    profile = skill_profile_repository.get(workspace_id)
    source = "saved"
    if profile is None:
        profile = default_skill_profile(workspace_id)
        source = "default"
    instructions = [
        SkillPromptInstruction(name=skill.name, instruction=skill.custom_instructions)
        for skill in profile.enabled_skills[:5]
    ]
    return instructions, source, profile.profile, profile.updated_at


def _skill_profile_context_from_request(workspace_id: str, skill_context):
    if skill_context:
        return (
            _to_skill_prompt_instructions(skill_context),
            "request",
            "temporary",
            None,
        )
    return _saved_skill_profile_context(workspace_id)


def _to_attached_documents(attached_documents) -> list[AttachedDocument]:
    return [
        AttachedDocument(name=item.name, content=item.content)
        for item in (attached_documents or [])
    ]


def _to_skill_prompt_instructions(skill_context) -> list[SkillPromptInstruction]:
    return [
        SkillPromptInstruction(
            name=item.name,
            instruction=item.custom_instructions,
        )
        for item in skill_context[:5]
    ]


def _ensure_conversation(workspace_id: str, conversation_id: str | None, title: str | None = None):
    if conversation_id:
        conversation = conversation_repository.get_conversation(workspace_id, conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation
    return conversation_repository.add_conversation(
        create_workspace_conversation(workspace_id, title=title)
    )


def _persist_answer_in_conversation(conversation_id: str, answer):
    conversation_repository.add_message(
        create_conversation_message(
            conversation_id=conversation_id,
            workspace_id=answer.workspace_id,
            role="user",
            content=answer.question,
        )
    )
    usage = answer.usage
    assistant_message = conversation_repository.add_message(
        create_conversation_message(
            conversation_id=conversation_id,
            workspace_id=answer.workspace_id,
            role="assistant",
            content=answer.answer,
            sources_count=len(answer.sources),
            used_context_chunks=answer.used_context_chunks,
            llm_provider=answer.llm_provider,
            llm_model=answer.llm_model,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            latency_ms=usage.latency_ms if usage else None,
            skill_profile=answer.skill_profile,
            sources=answer.sources,
        )
    )
    return replace(answer, conversation_message_id=assistant_message.id)


def _conversation_export_content(conversation, export_format: str) -> tuple[str, str]:
    normalized_format = (export_format or "markdown").lower()
    if normalized_format not in {"markdown", "text", "json"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format"
        )
    safe_title = "-".join(conversation.title.lower().split())[:80] or "conversation"
    filename = f"{safe_title}.{'md' if normalized_format == 'markdown' else normalized_format}"
    if normalized_format == "json":
        import json

        payload = to_workspace_conversation_response(conversation).model_dump()
        return filename, json.dumps(payload, indent=2, sort_keys=True)
    if normalized_format == "text":
        lines = [conversation.title, f"Workspace: {conversation.workspace_id}", ""]
        for message in conversation.messages:
            lines.extend([message.role.upper(), message.content, ""])
            if message.role == "assistant" and message.sources:
                lines.append("SOURCES")
                for source in message.sources:
                    lines.append(f"- {source.source_path} ({source.score:.2f})")
                lines.append("")
        return filename, "\n".join(lines).strip() + "\n"
    lines = [f"# {conversation.title}", "", f"Workspace: `{conversation.workspace_id}`", ""]
    for message in conversation.messages:
        heading = "User" if message.role == "user" else "Assistant"
        lines.extend([f"## {heading}", "", message.content, ""])
        if message.role == "assistant":
            meta = []
            if message.llm_provider:
                meta.append(f"model: `{message.llm_provider}/{message.llm_model or 'default'}`")
            if message.total_tokens is not None:
                meta.append(f"tokens: `{message.total_tokens}`")
            if message.skill_profile:
                meta.append(f"skills: `{', '.join(message.skill_profile.active_skills) or 'none'}`")
            if meta:
                lines.extend(["> " + " · ".join(meta), ""])
            if message.sources:
                lines.extend(["### Sources", ""])
                for index, source in enumerate(message.sources, start=1):
                    lines.extend(
                        [
                            f"{index}. `{source.source_path}` — score `{source.score:.2f}`",
                            "",
                            f"> {source.preview[:280]}",
                            "",
                        ]
                    )
    return filename, "\n".join(lines).strip() + "\n"


def _find_message_pair(conversation, message_id: str):
    for index, message in enumerate(conversation.messages):
        if message.id != message_id:
            continue
        previous_message = conversation.messages[index - 1] if index > 0 else None
        return message, previous_message
    return None, None


@router.post("/{workspace_id}/conversations", response_model=WorkspaceConversationResponse)
def create_workspace_conversation_endpoint(
    workspace_id: str,
    request: CreateConversationRequest | None = None,
) -> WorkspaceConversationResponse:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    conversation = conversation_repository.add_conversation(
        create_workspace_conversation(
            workspace_id,
            title=request.title if request else None,
        )
    )
    return to_workspace_conversation_response(conversation)


@router.get("/{workspace_id}/conversations", response_model=list[WorkspaceConversationResponse])
def list_workspace_conversations(
    workspace_id: str,
    limit: int = 30,
    include_archived: bool = False,
    search: str | None = None,
    pinned_only: bool = False,
) -> list[WorkspaceConversationResponse]:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    conversations = conversation_repository.list_conversations(
        workspace_id,
        limit=limit,
        include_archived=include_archived,
        search=search,
        pinned_only=pinned_only,
    )
    return [
        to_workspace_conversation_response(conversation, include_messages=False)
        for conversation in conversations
    ]


@router.get(
    "/{workspace_id}/conversations/{conversation_id}", response_model=WorkspaceConversationResponse
)
def get_workspace_conversation(
    workspace_id: str,
    conversation_id: str,
) -> WorkspaceConversationResponse:
    conversation = conversation_repository.get_conversation(workspace_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return to_workspace_conversation_response(conversation)


@router.patch(
    "/{workspace_id}/conversations/{conversation_id}", response_model=WorkspaceConversationResponse
)
def update_workspace_conversation(
    workspace_id: str,
    conversation_id: str,
    request: UpdateConversationRequest,
) -> WorkspaceConversationResponse:
    conversation = conversation_repository.update_conversation_title(
        workspace_id,
        conversation_id,
        request.title,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return to_workspace_conversation_response(conversation)


@router.patch(
    "/{workspace_id}/conversations/{conversation_id}/pin",
    response_model=WorkspaceConversationResponse,
)
def pin_workspace_conversation(
    workspace_id: str,
    conversation_id: str,
    request: ConversationPinRequest,
) -> WorkspaceConversationResponse:
    conversation = conversation_repository.set_conversation_pinned(
        workspace_id,
        conversation_id,
        request.pinned,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return to_workspace_conversation_response(conversation)


@router.patch(
    "/{workspace_id}/conversations/{conversation_id}/archive",
    response_model=WorkspaceConversationResponse,
)
def archive_workspace_conversation(
    workspace_id: str,
    conversation_id: str,
    request: ConversationArchiveRequest,
) -> WorkspaceConversationResponse:
    conversation = conversation_repository.set_conversation_archived(
        workspace_id,
        conversation_id,
        request.archived,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return to_workspace_conversation_response(conversation)


@router.get(
    "/{workspace_id}/conversations/{conversation_id}/export",
    response_model=ConversationExportResponse,
)
def export_workspace_conversation(
    workspace_id: str,
    conversation_id: str,
    format: str = "markdown",
) -> ConversationExportResponse:
    conversation = conversation_repository.get_conversation(workspace_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    filename, content = _conversation_export_content(conversation, format)
    return ConversationExportResponse(
        conversation_id=conversation.id,
        format=format.lower(),
        filename=filename,
        content=content,
    )


@router.get("/{workspace_id}/answer-notes", response_model=list[ConversationAnswerNoteResponse])
def list_workspace_answer_notes(
    workspace_id: str,
    limit: int = 30,
    search: str | None = None,
    pinned_only: bool = False,
    source_path: str | None = None,
) -> list[ConversationAnswerNoteResponse]:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return [
        to_answer_note_response(note)
        for note in conversation_repository.list_answer_notes(
            workspace_id,
            limit=limit,
            search=search,
            pinned_only=pinned_only,
            source_path=source_path,
        )
    ]


@router.post(
    "/{workspace_id}/conversations/{conversation_id}/messages/{message_id}/note",
    response_model=ConversationAnswerNoteResponse,
)
def save_conversation_answer_note(
    workspace_id: str,
    conversation_id: str,
    message_id: str,
    request: SaveAnswerNoteRequest,
) -> ConversationAnswerNoteResponse:
    conversation = conversation_repository.get_conversation(workspace_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    message, previous_message = _find_message_pair(conversation, message_id)
    if message is None or message.role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assistant message not found"
        )
    content = (request.content or message.content).strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Note content cannot be empty"
        )
    note = conversation_repository.add_answer_note(
        create_conversation_answer_note(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            message_id=message_id,
            title=request.title or conversation.title,
            content=content,
            source_question=previous_message.content
            if previous_message and previous_message.role == "user"
            else None,
            source_paths=[source.source_path for source in message.sources],
        )
    )
    return to_answer_note_response(note)


@router.patch(
    "/{workspace_id}/answer-notes/{note_id}", response_model=ConversationAnswerNoteResponse
)
def update_workspace_answer_note(
    workspace_id: str,
    note_id: str,
    request: UpdateAnswerNoteRequest,
) -> ConversationAnswerNoteResponse:
    note = conversation_repository.update_answer_note(
        workspace_id,
        note_id,
        title=request.title,
        content=request.content,
        pinned=request.pinned,
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer note not found")
    return to_answer_note_response(note)


@router.patch(
    "/{workspace_id}/answer-notes/{note_id}/pin", response_model=ConversationAnswerNoteResponse
)
def pin_workspace_answer_note(
    workspace_id: str,
    note_id: str,
    request: AnswerNotePinRequest,
) -> ConversationAnswerNoteResponse:
    note = conversation_repository.update_answer_note(
        workspace_id,
        note_id,
        pinned=request.pinned,
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer note not found")
    return to_answer_note_response(note)


@router.get(
    "/{workspace_id}/conversations/{conversation_id}/context-preview",
    response_model=ConversationContextPreviewResponse,
)
def get_conversation_context_preview(
    workspace_id: str,
    conversation_id: str,
) -> ConversationContextPreviewResponse:
    conversation = conversation_repository.get_conversation(workspace_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    notes = conversation_repository.list_answer_notes(workspace_id, limit=50, search=None)
    conversation_notes = [note for note in notes if note.conversation_id == conversation.id]
    questions = [message.content for message in conversation.messages if message.role == "user"]
    answers = [message.content for message in conversation.messages if message.role == "assistant"]
    source_paths = sorted(
        {
            source.source_path
            for message in conversation.messages
            for source in message.sources
            if source.source_path
        }
        | {
            source_path
            for note in conversation_notes
            for source_path in note.source_paths
            if source_path
        }
    )
    latest_questions = questions[-3:]
    latest_notes = conversation_notes[:5]
    reusable_lines = [
        f"Conversation: {conversation.title}",
        f"Questions: {len(questions)}",
        f"Answers: {len(answers)}",
    ]
    if latest_questions:
        reusable_lines.extend(["", "Recent questions:"])
        reusable_lines.extend(f"- {question}" for question in latest_questions)
    if latest_notes:
        reusable_lines.extend(["", "Saved notes:"])
        reusable_lines.extend(f"- {note.title}: {note.content[:220]}" for note in latest_notes)
    if source_paths:
        reusable_lines.extend(["", "Source paths:"])
        reusable_lines.extend(f"- {source_path}" for source_path in source_paths[:12])
    return ConversationContextPreviewResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        questions_count=len(questions),
        answers_count=len(answers),
        notes_count=len(conversation_notes),
        source_paths=source_paths,
        reusable_context="\n".join(reusable_lines),
        safety_note="This is a preparation preview only. It does not automatically inject conversation history into Ask.",
    )


@router.delete("/{workspace_id}/answer-notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_answer_note(workspace_id: str, note_id: str) -> None:
    if not conversation_repository.delete_answer_note(workspace_id, note_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer note not found")


@router.delete(
    "/{workspace_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_workspace_conversation(
    workspace_id: str,
    conversation_id: str,
) -> None:
    if not conversation_repository.delete_conversation(workspace_id, conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post("/{workspace_id}/ask", response_model=WorkspaceQuestionAnswerResponse)
def ask_workspace_question(
    workspace_id: str,
    request: AskWorkspaceQuestionRequest,
) -> WorkspaceQuestionAnswerResponse:
    logger.info(
        "workspace ask requested workspace_id=%s mode=override_or_default limit=%s",
        workspace_id,
        request.limit,
    )
    use_case = AskWorkspaceQuestionUseCase(
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider_factory=llm_provider_factory,
        index_status_repository=index_status_repository,
        timeline_repository=timeline_repository,
        reranker=build_reranker(),
        conversation_repository=conversation_repository,
        project_context_provider=project_context_composer,
    )

    try:
        conversation = _ensure_conversation(
            workspace_id,
            request.conversation_id,
            title=request.question,
        )
        skill_instructions, skill_source, skill_profile_name, skill_updated_at = (
            _skill_profile_context_from_request(workspace_id, request.skill_context)
        )
        result = use_case.execute(
            AskWorkspaceQuestionInput(
                workspace_id=workspace_id,
                question=request.question,
                limit=request.limit,
                llm_provider_override=request.llm_provider,
                llm_model_override=request.llm_model,
                skill_instructions=skill_instructions,
                skill_profile_source=skill_source,
                skill_profile_name=skill_profile_name,
                skill_profile_updated_at=skill_updated_at,
                conversation_id=conversation.id,
                images=request.images,
                temperature=request.temperature,
                think=request.think,
                attached_documents=_to_attached_documents(request.attached_documents),
            )
        )
        result = _persist_answer_in_conversation(conversation.id, result)
    except AskWorkspaceQuestionNotFoundError as exc:
        logger.warning(
            "workspace ask rejected workspace_id=%s mode=override_or_default reason=%s",
            workspace_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AskWorkspaceQuestionValidationError as exc:
        logger.warning(
            "workspace ask rejected workspace_id=%s mode=override_or_default reason=%s",
            workspace_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info(
        "workspace ask completed workspace_id=%s mode=override_or_default provider=%s model=%s "
        "retrieved_chunks=%s diagnostic_code=%s quality_warnings=%s",
        workspace_id,
        result.llm_provider,
        result.llm_model,
        result.used_context_chunks,
        result.diagnostic_code or "none",
        len(result.quality_warnings),
    )
    return to_workspace_question_answer_response(result)


@router.post(
    "/{workspace_id}/ask-selected",
    response_model=WorkspaceQuestionAnswerResponse,
)
def ask_workspace_question_with_selected_llm(
    workspace_id: str,
    request: AskWorkspaceQuestionWithSelectedLLMRequest,
) -> WorkspaceQuestionAnswerResponse:
    logger.info(
        "workspace ask requested workspace_id=%s mode=selected_llm limit=%s",
        workspace_id,
        request.limit,
    )
    ask_use_case = AskWorkspaceQuestionUseCase(
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider_factory=llm_provider_factory,
        index_status_repository=index_status_repository,
        timeline_repository=timeline_repository,
        reranker=build_reranker(),
        conversation_repository=conversation_repository,
        project_context_provider=project_context_composer,
    )
    use_case = AskWorkspaceQuestionWithSelectedLLMUseCase(
        workspace_repository=workspace_repository,
        selection_repository=workspace_model_selection_repository,
        llm_provider_factory=llm_provider_factory,
        ask_workspace_question=ask_use_case,
        configuration=readiness_configuration,
    )

    try:
        conversation = _ensure_conversation(
            workspace_id,
            request.conversation_id,
            title=request.question,
        )
        skill_instructions, skill_source, skill_profile_name, skill_updated_at = (
            _skill_profile_context_from_request(workspace_id, request.skill_context)
        )
        result = use_case.execute(
            AskWorkspaceQuestionWithSelectedLLMInput(
                workspace_id=workspace_id,
                question=request.question,
                limit=request.limit,
                skill_instructions=skill_instructions,
                skill_profile_source=skill_source,
                skill_profile_name=skill_profile_name,
                skill_profile_updated_at=skill_updated_at,
                conversation_id=conversation.id,
                images=request.images,
                temperature=request.temperature,
                think=request.think,
                attached_documents=_to_attached_documents(request.attached_documents),
            )
        )
        result = _persist_answer_in_conversation(conversation.id, result)
    except AskWorkspaceQuestionWithSelectedLLMNotFoundError as exc:
        logger.warning(
            "workspace ask rejected workspace_id=%s mode=selected_llm reason=%s",
            workspace_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AskWorkspaceQuestionWithSelectedLLMValidationError as exc:
        logger.warning(
            "workspace ask rejected workspace_id=%s mode=selected_llm reason=%s",
            workspace_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info(
        "workspace ask completed workspace_id=%s mode=selected_llm provider=%s model=%s "
        "retrieved_chunks=%s diagnostic_code=%s quality_warnings=%s",
        workspace_id,
        result.llm_provider,
        result.llm_model,
        result.used_context_chunks,
        result.diagnostic_code or "none",
        len(result.quality_warnings),
    )
    return to_workspace_question_answer_response(result)


def _current_selected_llm_label(workspace_id: str) -> str | None:
    """Return the `provider/model` label of the workspace's selected LLM, if any."""
    selection = workspace_model_selection_repository.get(workspace_id)
    selected_llm = selection.selected_llm if selection is not None else None
    if selected_llm is None:
        return None
    if selected_llm.model:
        return f"{selected_llm.provider}/{selected_llm.model}"
    return selected_llm.provider


@router.get(
    "/{workspace_id}/git-insights",
    response_model=GitInsightsResponse,
)
def get_workspace_git_insights(workspace_id: str) -> GitInsightsResponse:
    use_case = GetWorkspaceGitInsightsUseCase(
        workspace_repository=workspace_repository,
        git_history=git_history,
    )
    try:
        insights = use_case.execute(GetWorkspaceGitInsightsInput(workspace_id=workspace_id))
    except WorkspaceGitInsightsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_git_insights_response(insights)


@router.get(
    "/{workspace_id}/todos",
    response_model=ProjectTodosResponse,
)
def get_workspace_todos(workspace_id: str) -> ProjectTodosResponse:
    resolved_rules = _resolve_file_rules(workspace_id, None)
    use_case = GetWorkspaceTodosUseCase(
        workspace_repository=workspace_repository,
        file_system=file_system,
        scan_use_case=ScanProjectUseCase(file_system),
    )
    try:
        todos = use_case.execute(
            GetWorkspaceTodosInput(
                workspace_id=workspace_id,
                include_patterns=resolved_rules.include_patterns,
                exclude_patterns=resolved_rules.exclude_patterns,
            )
        )
    except WorkspaceTodosNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_project_todos_response(todos)


@router.get(
    "/{workspace_id}/understanding",
    response_model=ProjectUnderstandingResponse,
)
def get_workspace_understanding(workspace_id: str) -> ProjectUnderstandingResponse:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    understanding = project_understanding_repository.get(workspace_id)
    if understanding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No project understanding has been generated for this workspace "
                "yet. Generate one first."
            ),
        )
    current_label = _current_selected_llm_label(workspace_id)
    is_stale = current_label is not None and current_label != understanding.model
    return to_project_understanding_response(understanding, is_stale=is_stale)


@router.post(
    "/{workspace_id}/understanding",
    response_model=ProjectUnderstandingResponse,
)
def generate_workspace_understanding(
    workspace_id: str,
) -> ProjectUnderstandingResponse:
    logger.info(
        "workspace understanding requested workspace_id=%s",
        workspace_id,
    )
    use_case = GenerateProjectUnderstandingUseCase(
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider_factory=llm_provider_factory,
        index_status_repository=index_status_repository,
        selection_repository=workspace_model_selection_repository,
        understanding_repository=project_understanding_repository,
    )
    try:
        understanding = use_case.execute(
            GenerateProjectUnderstandingInput(workspace_id=workspace_id)
        )
    except GenerateProjectUnderstandingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except GenerateProjectUnderstandingValidationError as exc:
        logger.warning(
            "workspace understanding rejected workspace_id=%s reason=%s",
            workspace_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info(
        "workspace understanding completed workspace_id=%s model=%s risks=%s sources=%s",
        workspace_id,
        understanding.model,
        len(understanding.risks),
        len(understanding.sources),
    )
    return to_project_understanding_response(understanding, is_stale=False)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{workspace_id}/ask-selected/stream")
def ask_workspace_question_with_selected_llm_stream(
    workspace_id: str,
    request: AskWorkspaceQuestionWithSelectedLLMRequest,
) -> StreamingResponse:
    logger.info(
        "workspace ask requested workspace_id=%s mode=selected_llm_stream limit=%s",
        workspace_id,
        request.limit,
    )
    ask_use_case = AskWorkspaceQuestionUseCase(
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider_factory=llm_provider_factory,
        index_status_repository=index_status_repository,
        timeline_repository=timeline_repository,
        reranker=build_reranker(),
        conversation_repository=conversation_repository,
        project_context_provider=project_context_composer,
    )
    use_case = AskWorkspaceQuestionWithSelectedLLMUseCase(
        workspace_repository=workspace_repository,
        selection_repository=workspace_model_selection_repository,
        llm_provider_factory=llm_provider_factory,
        ask_workspace_question=ask_use_case,
        configuration=readiness_configuration,
    )

    # Conversation + skill context resolution can raise; do it before streaming so
    # the client gets a normal HTTP error instead of a half-open stream.
    conversation = _ensure_conversation(
        workspace_id,
        request.conversation_id,
        title=request.question,
    )
    skill_instructions, skill_source, skill_profile_name, skill_updated_at = (
        _skill_profile_context_from_request(workspace_id, request.skill_context)
    )
    ask_input = AskWorkspaceQuestionWithSelectedLLMInput(
        workspace_id=workspace_id,
        question=request.question,
        limit=request.limit,
        skill_instructions=skill_instructions,
        skill_profile_source=skill_source,
        skill_profile_name=skill_profile_name,
        skill_profile_updated_at=skill_updated_at,
        conversation_id=conversation.id,
        images=request.images,
        temperature=request.temperature,
        think=request.think,
        attached_documents=_to_attached_documents(request.attached_documents),
    )

    def event_stream():
        try:
            for event in use_case.execute_stream(ask_input):
                if isinstance(event, AskStreamDelta):
                    yield _sse_event("token", {"text": event.text})
                elif isinstance(event, AskStreamFinal):
                    final = _persist_answer_in_conversation(conversation.id, event.answer)
                    payload = to_workspace_question_answer_response(final).model_dump(mode="json")
                    yield _sse_event("final", payload)
        except (
            AskWorkspaceQuestionWithSelectedLLMNotFoundError,
            AskWorkspaceQuestionWithSelectedLLMValidationError,
        ) as exc:
            logger.warning(
                "workspace ask rejected workspace_id=%s mode=selected_llm_stream reason=%s",
                workspace_id,
                exc,
            )
            yield _sse_event("error", {"detail": str(exc)})
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            logger.exception(
                "workspace ask failed workspace_id=%s mode=selected_llm_stream",
                workspace_id,
            )
            yield _sse_event("error", {"detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    "/{workspace_id}/readiness",
    response_model=WorkspaceReadinessResponse,
)
def get_workspace_readiness(workspace_id: str) -> WorkspaceReadinessResponse:
    use_case = GetWorkspaceReadinessUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        index_status_repository=index_status_repository,
        command_repository=command_repository,
        configuration=readiness_configuration,
    )

    try:
        readiness = use_case.execute(GetWorkspaceReadinessInput(workspace_id=workspace_id))
    except WorkspaceReadinessNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_readiness_response(readiness)


@router.get(
    "/{workspace_id}/quick-start",
    response_model=WorkspaceQuickStartResponse,
)
def get_workspace_quick_start(workspace_id: str) -> WorkspaceQuickStartResponse:
    use_case = GetWorkspaceQuickStartUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        index_status_repository=index_status_repository,
        configuration=readiness_configuration,
    )

    try:
        quick_start = use_case.execute(GetWorkspaceQuickStartInput(workspace_id=workspace_id))
    except WorkspaceQuickStartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_quick_start_response(quick_start)


@router.get(
    "/{workspace_id}/dashboard",
    response_model=WorkspaceDashboardResponse,
)
def get_workspace_dashboard(workspace_id: str) -> WorkspaceDashboardResponse:
    use_case = GetWorkspaceDashboardUseCase(
        summary_use_case=GetWorkspaceSummaryUseCase(
            workspace_repository=workspace_repository,
            project_scan_repository=project_scan_repository,
            command_repository=command_repository,
            index_status_repository=index_status_repository,
            timeline_repository=timeline_repository,
        ),
        readiness_use_case=GetWorkspaceReadinessUseCase(
            workspace_repository=workspace_repository,
            project_scan_repository=project_scan_repository,
            index_status_repository=index_status_repository,
            command_repository=command_repository,
            configuration=readiness_configuration,
        ),
        quick_start_use_case=GetWorkspaceQuickStartUseCase(
            workspace_repository=workspace_repository,
            project_scan_repository=project_scan_repository,
            index_status_repository=index_status_repository,
            configuration=readiness_configuration,
        ),
        assistant_recommendation_use_case=GetWorkspaceAssistantRecommendationUseCase(
            workspace_repository=workspace_repository,
            project_scan_repository=project_scan_repository,
            index_status_repository=index_status_repository,
            configuration=readiness_configuration,
        ),
        timeline_use_case=ListWorkspaceTimelineUseCase(
            workspace_repository=workspace_repository,
            timeline_repository=timeline_repository,
        ),
        runtime_health_use_case=GetRuntimeHealthUseCase(
            health_checkers=runtime_health_checkers,
            configuration=runtime_health_configuration,
        ),
        models_summary_use_case=GetWorkspaceModelsDashboardSummaryUseCase(
            dashboard_use_case=_build_workspace_models_dashboard_use_case()
        ),
    )

    try:
        dashboard = use_case.execute(GetWorkspaceDashboardInput(workspace_id=workspace_id))
    except WorkspaceDashboardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_dashboard_response(dashboard)


@router.get(
    "/{workspace_id}/ui-actions",
    response_model=WorkspaceUIActionCatalogResponse,
)
def get_workspace_ui_actions(
    workspace_id: str,
) -> WorkspaceUIActionCatalogResponse:
    use_case = GetWorkspaceUIActionsUseCase(
        workspace_repository=workspace_repository,
        quick_start_use_case=GetWorkspaceQuickStartUseCase(
            workspace_repository=workspace_repository,
            project_scan_repository=project_scan_repository,
            index_status_repository=index_status_repository,
            configuration=readiness_configuration,
        ),
        readiness_use_case=GetWorkspaceReadinessUseCase(
            workspace_repository=workspace_repository,
            project_scan_repository=project_scan_repository,
            index_status_repository=index_status_repository,
            command_repository=command_repository,
            configuration=readiness_configuration,
        ),
        models_summary_use_case=GetWorkspaceModelsDashboardSummaryUseCase(
            dashboard_use_case=_build_workspace_models_dashboard_use_case()
        ),
    )
    try:
        catalog = use_case.execute(GetWorkspaceUIActionsInput(workspace_id=workspace_id))
    except WorkspaceUIActionsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelRecommendationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_workspace_ui_action_catalog_response(catalog)


@router.get(
    "/{workspace_id}/local-ai/activation-guide",
    response_model=LocalAIActivationGuideResponse,
)
def get_local_ai_activation_guide(
    workspace_id: str,
) -> LocalAIActivationGuideResponse:
    try:
        guide = GetLocalAIActivationGuideUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            index_status_repository=index_status_repository,
            configuration=runtime_health_configuration,
        ).execute(GetLocalAIActivationGuideInput(workspace_id=workspace_id))
    except LocalAIActivationGuideNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_local_ai_activation_guide_response(guide)


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
        report = use_case.execute(GenerateProjectOverviewReportInput(workspace_id=workspace_id))
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
    "/{workspace_id}/reports/catalog",
    response_model=ReportCatalogResponse,
)
def get_workspace_report_catalog(workspace_id: str) -> ReportCatalogResponse:
    try:
        catalog = GetWorkspaceReportCatalogUseCase(
            workspace_repository=workspace_repository,
        ).execute(GetWorkspaceReportCatalogInput(workspace_id=workspace_id))
    except WorkspaceReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_report_catalog_response(catalog)


@router.post(
    "/{workspace_id}/reports/{report_type}/save",
    response_model=SavedWorkspaceReportResponse,
)
def save_workspace_report(
    workspace_id: str,
    report_type: str,
) -> SavedWorkspaceReportResponse:
    generator = GenerateWorkspaceReportUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
        conversation_repository=conversation_repository,
        timeline_repository=timeline_repository,
    )
    use_case = SaveWorkspaceReportUseCase(
        report_generator=generator,
        report_repository=report_repository,
    )
    try:
        saved = use_case.execute(
            SaveWorkspaceReportInput(
                workspace_id=workspace_id,
                report_type=report_type,
            )
        )
    except WorkspaceReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkspaceReportScanRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except WorkspaceReportTypeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_saved_workspace_report_response(saved)


@router.post(
    "/{workspace_id}/reports/custom-preview",
    response_model=ProjectOverviewReportResponse,
)
def build_custom_workspace_report_preview(
    workspace_id: str,
    request: BuildCustomWorkspaceReportRequest,
) -> ProjectOverviewReportResponse:
    report = _build_custom_workspace_report(workspace_id, request)
    return to_project_overview_report_response(report)


@router.post(
    "/{workspace_id}/reports/custom-save",
    response_model=SavedWorkspaceReportResponse,
)
def save_custom_workspace_report(
    workspace_id: str,
    request: SaveCustomWorkspaceReportRequest,
) -> SavedWorkspaceReportResponse:
    report = _build_custom_workspace_report(workspace_id, request)
    saved = report_repository.add_report(create_saved_workspace_report(report))
    return to_saved_workspace_report_response(saved)


@router.post(
    "/{workspace_id}/reports/draft-save",
    response_model=SavedWorkspaceReportResponse,
)
def save_edited_workspace_report(
    workspace_id: str,
    request: SaveEditedWorkspaceReportRequest,
) -> SavedWorkspaceReportResponse:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    sections = [
        ReportSection(
            title=section.title,
            content=section.content,
            bullets=list(section.bullets),
        )
        for section in request.sections
    ]
    saved = report_repository.add_report(
        create_saved_workspace_report_from_draft(
            workspace_id=workspace_id,
            report_type=request.report_type,
            title=request.title,
            summary=request.summary,
            sections=sections,
            generated_from=request.generated_from,
            export_markdown=request.export_markdown,
            safety_note=request.safety_note,
        )
    )
    return to_saved_workspace_report_response(saved)


def _build_custom_workspace_report(
    workspace_id: str,
    request: BuildCustomWorkspaceReportRequest,
) -> ProjectOverviewReport:
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    selected_note_ids = set(request.note_ids)
    selected_conversation_ids = set(request.conversation_ids)
    notes = [
        note
        for note in conversation_repository.list_answer_notes(workspace_id, limit=200)
        if not selected_note_ids or note.id in selected_note_ids
    ]
    conversations = [
        conversation_repository.get_conversation(workspace_id, conversation_id)
        for conversation_id in selected_conversation_ids
    ]
    conversations = [conversation for conversation in conversations if conversation is not None]

    source_paths = sorted({path for note in notes for path in note.source_paths})
    recent_questions: list[str] = []
    answer_previews: list[str] = []
    for conversation in conversations:
        for message in conversation.messages:
            if message.role == "user" and len(recent_questions) < 8:
                recent_questions.append(message.content[:220])
            elif message.role == "assistant" and len(answer_previews) < 6:
                answer_previews.append(message.content[:260])
            for source in message.sources:
                if source.source_path:
                    source_paths.append(source.source_path)
    source_paths = sorted(dict.fromkeys(source_paths))

    title = (request.title or "Custom workspace report").strip()[:180] or "Custom workspace report"
    summary = (
        request.summary
        or "Custom report assembled from selected saved notes, conversations, and local workspace evidence."
    ).strip()

    sections = [
        ReportSection(
            title="Source boundaries",
            content="This custom report is assembled from explicit user-selected workspace context.",
            bullets=[
                "No shell commands are executed.",
                "No scan, index, rebuild, upload, or model change is triggered.",
                "Selected notes and conversations guide the draft; verify source-backed claims before sharing.",
            ],
        ),
        ReportSection(
            title="Selected notes",
            content=f"Selected reusable notes: {len(notes)}.",
            bullets=[f"{note.title}: {note.content[:240]}" for note in notes[:12]]
            or ["No saved notes selected."],
        ),
        ReportSection(
            title="Selected conversations",
            content=f"Selected conversations: {len(conversations)}.",
            bullets=[
                f"{conversation.title}: {len(conversation.messages)} messages"
                for conversation in conversations[:8]
            ]
            or ["No conversations selected."],
        ),
        ReportSection(
            title="Reusable findings",
            content="Condensed snippets from the selected context.",
            bullets=(recent_questions[:4] + answer_previews[:4])
            or ["No reusable findings were available in the selected context."],
        ),
        ReportSection(
            title="Captured sources",
            content="Source paths captured from selected notes and conversations.",
            bullets=source_paths[:20] or ["No source paths captured."],
        ),
    ]
    extra_context = (request.extra_context or "").strip()
    if extra_context:
        sections.append(
            ReportSection(
                title="User drafting notes",
                content="Additional user-provided drafting context.",
                bullets=[line.strip() for line in extra_context.splitlines() if line.strip()][:12]
                or [extra_context[:500]],
            )
        )

    draft = ProjectOverviewReport(
        workspace_id=workspace_id,
        title=title,
        summary=summary,
        sections=sections,
        generated_from=[
            "selected_answer_notes",
            "selected_conversations",
            "captured_source_paths",
            "manual_drafting_context",
        ],
        report_type=(request.report_type or "custom_report").strip().lower().replace("-", "_")
        or "custom_report",
        safety_note=(
            "Custom report builder is read-only. It uses selected saved context and does not execute commands, "
            "scan, index, rebuild, upload, or change models."
        ),
    )
    return ProjectOverviewReport(
        workspace_id=draft.workspace_id,
        title=draft.title,
        summary=draft.summary,
        sections=draft.sections,
        generated_from=draft.generated_from,
        report_type=draft.report_type,
        export_markdown=render_report_markdown(draft),
        safety_note=draft.safety_note,
    )


@router.get(
    "/{workspace_id}/reports/saved",
    response_model=list[SavedWorkspaceReportResponse],
)
def list_saved_workspace_reports(
    workspace_id: str,
    search: str | None = None,
    report_type: str | None = None,
    pinned_only: bool = False,
) -> list[SavedWorkspaceReportResponse]:
    use_case = ListSavedWorkspaceReportsUseCase(
        workspace_repository=workspace_repository,
        report_repository=report_repository,
    )
    try:
        reports = use_case.execute(
            ListSavedWorkspaceReportsInput(
                workspace_id=workspace_id,
                search=search,
                report_type=report_type,
                pinned_only=pinned_only,
            )
        )
    except SavedWorkspaceReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [to_saved_workspace_report_response(report) for report in reports]


@router.get(
    "/{workspace_id}/reports/saved/{report_id}",
    response_model=SavedWorkspaceReportResponse,
)
def get_saved_workspace_report(
    workspace_id: str,
    report_id: str,
) -> SavedWorkspaceReportResponse:
    use_case = GetSavedWorkspaceReportUseCase(
        workspace_repository=workspace_repository,
        report_repository=report_repository,
    )
    try:
        report = use_case.execute(
            GetSavedWorkspaceReportInput(workspace_id=workspace_id, report_id=report_id)
        )
    except SavedWorkspaceReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_saved_workspace_report_response(report)


@router.patch(
    "/{workspace_id}/reports/saved/{report_id}",
    response_model=SavedWorkspaceReportResponse,
)
def update_saved_workspace_report(
    workspace_id: str,
    report_id: str,
    request: UpdateSavedWorkspaceReportRequest,
) -> SavedWorkspaceReportResponse:
    use_case = UpdateSavedWorkspaceReportUseCase(
        workspace_repository=workspace_repository,
        report_repository=report_repository,
    )
    try:
        report = use_case.execute(
            UpdateSavedWorkspaceReportInput(
                workspace_id=workspace_id,
                report_id=report_id,
                title=request.title,
                summary=request.summary,
                export_markdown=request.export_markdown,
                export_text=request.export_text
                or (
                    markdown_to_plain_text(request.export_markdown)
                    if request.export_markdown
                    else None
                ),
                report_json=request.report_json,
                generated_from=request.generated_from,
            )
        )
    except SavedWorkspaceReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_saved_workspace_report_response(report)


@router.patch(
    "/{workspace_id}/reports/saved/{report_id}/pin",
    response_model=SavedWorkspaceReportResponse,
)
def pin_saved_workspace_report(
    workspace_id: str,
    report_id: str,
    request: SavedReportPinRequest,
) -> SavedWorkspaceReportResponse:
    use_case = UpdateSavedWorkspaceReportUseCase(
        workspace_repository=workspace_repository,
        report_repository=report_repository,
    )
    try:
        report = use_case.execute(
            UpdateSavedWorkspaceReportInput(
                workspace_id=workspace_id,
                report_id=report_id,
                pinned=request.pinned,
            )
        )
    except SavedWorkspaceReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_saved_workspace_report_response(report)


@router.delete(
    "/{workspace_id}/reports/saved/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_saved_workspace_report(
    workspace_id: str,
    report_id: str,
) -> None:
    use_case = DeleteSavedWorkspaceReportUseCase(
        workspace_repository=workspace_repository,
        report_repository=report_repository,
    )
    try:
        use_case.execute(
            DeleteSavedWorkspaceReportInput(workspace_id=workspace_id, report_id=report_id)
        )
    except SavedWorkspaceReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{workspace_id}/reports/{report_type}",
    response_model=ProjectOverviewReportResponse,
)
def generate_workspace_report(
    workspace_id: str,
    report_type: str,
) -> ProjectOverviewReportResponse:
    use_case = GenerateWorkspaceReportUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
        conversation_repository=conversation_repository,
        timeline_repository=timeline_repository,
    )
    try:
        report = use_case.execute(
            GenerateWorkspaceReportInput(
                workspace_id=workspace_id,
                report_type=report_type,
            )
        )
    except WorkspaceReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkspaceReportScanRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WorkspaceReportTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
        result = use_case.execute(BackfillWorkspaceTimelineInput(workspace_id=workspace_id))
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
    "/{workspace_id}/model-experiments",
    response_model=list[ModelExperimentRunResponse],
)
def list_workspace_model_experiments(
    workspace_id: str,
    limit: int = 20,
) -> list[ModelExperimentRunResponse]:
    try:
        runs = ListWorkspaceModelExperimentsUseCase(
            workspace_repository=workspace_repository,
            model_experiment_repository=model_experiment_repository,
        ).execute(
            ListWorkspaceModelExperimentsInput(
                workspace_id=workspace_id,
                limit=limit,
            )
        )
    except WorkspaceModelExperimentsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [to_model_experiment_run_response(run) for run in runs]


@router.get(
    "/{workspace_id}/model-performance",
    response_model=ModelPerformanceSummaryResponse,
)
def get_workspace_model_performance(
    workspace_id: str,
    limit: int = 20,
) -> ModelPerformanceSummaryResponse:
    try:
        summary = GetModelPerformanceSummaryUseCase(
            workspace_repository=workspace_repository,
            model_experiment_repository=model_experiment_repository,
            rating_repository=model_experiment_rating_repository,
        ).execute(
            GetModelPerformanceSummaryInput(
                workspace_id=workspace_id,
                limit=limit,
            )
        )
    except ModelPerformanceWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_model_performance_summary_response(summary)


@router.post(
    "/{workspace_id}/models/recommend",
    response_model=WorkspaceModelRecommendationResultResponse,
)
def recommend_workspace_models(
    workspace_id: str,
    request: RecommendWorkspaceModelsRequest,
) -> WorkspaceModelRecommendationResultResponse:
    try:
        result = RecommendWorkspaceModelsUseCase(
            workspace_repository=workspace_repository,
            model_experiment_repository=model_experiment_repository,
            rating_repository=model_experiment_rating_repository,
            model_catalog_registry=model_catalog_registry,
        ).execute(
            RecommendWorkspaceModelsInput(
                workspace_id=workspace_id,
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                task_type=request.task_type,
                model_type=request.model_type,
            )
        )
    except WorkspaceModelRecommendationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelRecommendationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_workspace_model_recommendation_result_response(result)


@router.post(
    "/{workspace_id}/models/explain",
    response_model=ModelRecommendationExplanationResponse,
)
def explain_workspace_model_recommendation(
    workspace_id: str,
    request: ExplainWorkspaceModelRecommendationRequest,
) -> ModelRecommendationExplanationResponse:
    try:
        explanation = ExplainWorkspaceModelRecommendationUseCase(
            workspace_repository=workspace_repository,
            model_experiment_repository=model_experiment_repository,
            rating_repository=model_experiment_rating_repository,
            model_catalog_registry=model_catalog_registry,
        ).execute(
            ExplainWorkspaceModelRecommendationInput(
                workspace_id=workspace_id,
                provider=request.provider,
                model=request.model,
                model_type=request.model_type,
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                task_type=request.task_type,
            )
        )
    except ModelRecommendationExplanationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelRecommendationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_model_recommendation_explanation_response(explanation)


@router.get(
    "/{workspace_id}/models/setup-guide",
    response_model=GuidedModelSetupGuideResponse,
)
def get_guided_model_setup(
    workspace_id: str,
) -> GuidedModelSetupGuideResponse:
    from app.adapters.system.hardware_probe import detect_total_ram_gb

    try:
        guide = GetGuidedModelSetupUseCase(
            workspace_repository=workspace_repository,
            model_catalog_registry=model_catalog_registry,
            total_ram_gb=detect_total_ram_gb(),
        ).execute(GetGuidedModelSetupInput(workspace_id=workspace_id))
    except GuidedModelSetupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_guided_model_setup_guide_response(guide)


@router.get(
    "/{workspace_id}/models/selection",
    response_model=WorkspaceModelSelectionResponse,
)
def get_workspace_model_selection(
    workspace_id: str,
) -> WorkspaceModelSelectionResponse:
    try:
        selection = GetWorkspaceModelSelectionUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            model_catalog_registry=model_catalog_registry,
            configuration=readiness_configuration,
        ).execute(GetWorkspaceModelSelectionInput(workspace_id=workspace_id))
    except WorkspaceModelSelectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_workspace_model_selection_response(selection)


@router.put(
    "/{workspace_id}/models/selection",
    response_model=WorkspaceModelSelectionResponse,
)
def update_workspace_model_selection(
    workspace_id: str,
    request: UpdateWorkspaceModelSelectionRequest,
) -> WorkspaceModelSelectionResponse:
    try:
        selection = UpdateWorkspaceModelSelectionUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            model_catalog_registry=model_catalog_registry,
            timeline_repository=timeline_repository,
            configuration=readiness_configuration,
        ).execute(
            UpdateWorkspaceModelSelectionInput(
                workspace_id=workspace_id,
                provider=request.provider,
                model=request.model,
                model_type=request.model_type,
                selected_reason=request.selected_reason,
            )
        )
    except UpdateWorkspaceModelSelectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UpdateWorkspaceModelSelectionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_workspace_model_selection_response(selection)


@router.get(
    "/{workspace_id}/models/selection/status",
    response_model=WorkspaceModelSelectionStatusResponse,
)
def get_workspace_model_selection_status(
    workspace_id: str,
) -> WorkspaceModelSelectionStatusResponse:
    try:
        selection_status = GetWorkspaceModelSelectionStatusUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            index_status_repository=index_status_repository,
            configuration=build_active_model_configuration(),
        ).execute(GetWorkspaceModelSelectionStatusInput(workspace_id=workspace_id))
    except WorkspaceModelSelectionStatusNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_workspace_model_selection_status_response(selection_status)


@router.get(
    "/{workspace_id}/models/usage-plan",
    response_model=SelectedModelUsagePlanResponse,
)
def get_selected_model_usage_plan(
    workspace_id: str,
) -> SelectedModelUsagePlanResponse:
    try:
        plan = GetSelectedModelUsagePlanUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            index_status_repository=index_status_repository,
            llm_provider_factory=llm_provider_factory,
            configuration=build_active_model_configuration(),
        ).execute(GetSelectedModelUsagePlanInput(workspace_id=workspace_id))
    except SelectedModelUsagePlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_selected_model_usage_plan_response(plan)


@router.get(
    "/{workspace_id}/models/embedding-indexing-plan",
    response_model=SelectedEmbeddingIndexingPlanResponse,
)
def get_selected_embedding_indexing_plan(
    workspace_id: str,
) -> SelectedEmbeddingIndexingPlanResponse:
    try:
        plan = GetSelectedEmbeddingIndexingPlanUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            index_status_repository=index_status_repository,
            configuration=readiness_configuration,
        ).execute(GetSelectedEmbeddingIndexingPlanInput(workspace_id=workspace_id))
    except SelectedEmbeddingIndexingPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_selected_embedding_indexing_plan_response(plan)


def _build_workspace_models_dashboard_use_case() -> GetWorkspaceModelsDashboardUseCase:
    # Use the LIVE active embedding (not the static env) so "matches active
    # runtime" is truthful after switching to the built-in llama.cpp engine.
    active_configuration = build_active_model_configuration()
    return GetWorkspaceModelsDashboardUseCase(
        workspace_repository=workspace_repository,
        selection_use_case=GetWorkspaceModelSelectionUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            model_catalog_registry=model_catalog_registry,
            configuration=active_configuration,
        ),
        selection_status_use_case=GetWorkspaceModelSelectionStatusUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            index_status_repository=index_status_repository,
            configuration=active_configuration,
        ),
        usage_plan_use_case=GetSelectedModelUsagePlanUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            index_status_repository=index_status_repository,
            llm_provider_factory=llm_provider_factory,
            configuration=active_configuration,
        ),
        embedding_indexing_plan_use_case=GetSelectedEmbeddingIndexingPlanUseCase(
            workspace_repository=workspace_repository,
            selection_repository=workspace_model_selection_repository,
            index_status_repository=index_status_repository,
            configuration=active_configuration,
        ),
        recommendation_use_case=RecommendWorkspaceModelsUseCase(
            workspace_repository=workspace_repository,
            model_experiment_repository=model_experiment_repository,
            rating_repository=model_experiment_rating_repository,
            model_catalog_registry=model_catalog_registry,
        ),
        performance_summary_use_case=GetModelPerformanceSummaryUseCase(
            workspace_repository=workspace_repository,
            model_experiment_repository=model_experiment_repository,
            rating_repository=model_experiment_rating_repository,
        ),
    )


@router.get(
    "/{workspace_id}/models/dashboard/summary",
    response_model=WorkspaceModelsDashboardSummaryResponse,
)
def get_workspace_models_dashboard_summary(
    workspace_id: str,
) -> WorkspaceModelsDashboardSummaryResponse:
    try:
        summary = GetWorkspaceModelsDashboardSummaryUseCase(
            dashboard_use_case=_build_workspace_models_dashboard_use_case()
        ).execute(GetWorkspaceModelsDashboardSummaryInput(workspace_id=workspace_id))
    except WorkspaceModelsDashboardSummaryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelRecommendationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_workspace_models_dashboard_summary_response(summary)


@router.get(
    "/{workspace_id}/models/dashboard",
    response_model=WorkspaceModelsDashboardResponse,
)
def get_workspace_models_dashboard(
    workspace_id: str,
) -> WorkspaceModelsDashboardResponse:
    use_case = _build_workspace_models_dashboard_use_case()
    try:
        dashboard = use_case.execute(GetWorkspaceModelsDashboardInput(workspace_id=workspace_id))
    except WorkspaceModelsDashboardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelRecommendationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_workspace_models_dashboard_response(dashboard)


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
