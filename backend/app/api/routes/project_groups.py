"""Project groups HTTP API.

A group treats several workspaces as one project. CRUD + membership here is a thin
wrapper over the manage use case; Ask fans a question across members; Overview
aggregates each member's facts and git into a single group view. Member
workspaces are only referenced — never created or deleted by these endpoints.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.dependencies import (
    build_reranker,
    conversation_repository,
    embedding_provider,
    git_history,
    index_manifest_repository,
    index_status_repository,
    llm_provider_factory,
    project_context_composer,
    project_graph_repository,
    project_group_repository,
    project_memory_repository,
    vector_store,
    workspace_repository,
)
from app.api.routes._conversation_persistence import ensure_conversation, persist_turn
from app.api.schemas.rag_schemas import (
    LLMUsageMetricsResponse,
    RagQualityWarningResponse,
    to_llm_usage_metrics_response,
    to_rag_quality_warning_response,
)
from app.core.domain.group_overview import GroupOverview
from app.core.domain.group_qa import GroupQuestionAnswer
from app.core.domain.project_group import ProjectGroup
from app.core.domain.project_memory import MemoryKind
from app.core.use_cases.ask_group_question import (
    AskGroupQuestionInput,
    AskGroupQuestionNotFoundError,
    AskGroupQuestionUseCase,
    AskGroupQuestionValidationError,
    GroupAskStreamDelta,
    GroupAskStreamFinal,
)
from app.core.use_cases.build_group_handbook import (
    BuildGroupHandbookNotFoundError,
    BuildGroupHandbookUseCase,
)
from app.core.use_cases.build_group_overview import (
    BuildGroupOverviewNotFoundError,
    BuildGroupOverviewUseCase,
)
from app.core.use_cases.manage_project_groups import (
    ManageProjectGroupsUseCase,
    ProjectGroupNotFoundError,
    ProjectGroupValidationError,
)
from app.core.use_cases.manage_project_memory import (
    AddMemoryInput,
    AddMemoryUseCase,
    AddMemoryValidationError,
    DeleteMemoryUseCase,
    ListMemoryUseCase,
    SetMemoryPinnedUseCase,
)

router = APIRouter(prefix="/workspace-groups", tags=["workspace-groups"])
logger = logging.getLogger(__name__)


def _manage() -> ManageProjectGroupsUseCase:
    return ManageProjectGroupsUseCase(project_group_repository)


# --- Schemas ---


class CreateGroupRequest(BaseModel):
    name: str
    workspace_ids: list[str] = Field(default_factory=list)


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    workspace_ids: list[str] | None = None


class AddMemberRequest(BaseModel):
    workspace_id: str


class GroupMemberRef(BaseModel):
    workspace_id: str
    name: str
    project_path: str


class GroupSummary(BaseModel):
    id: str
    name: str
    created_at: str
    member_count: int
    workspace_ids: list[str]


class GroupDetail(GroupSummary):
    members: list[GroupMemberRef]


class GroupListResponse(BaseModel):
    groups: list[GroupSummary]


def _live_workspace_ids(group: ProjectGroup) -> list[str]:
    """Member ids whose workspace still exists. A group only references
    workspaces, so a deleted workspace can leave a stale id behind — filtering
    here keeps the count and list honest (and self-heals old data)."""
    return [wid for wid in group.workspace_ids if workspace_repository.get(wid) is not None]


def _summary(group: ProjectGroup) -> GroupSummary:
    live_ids = _live_workspace_ids(group)
    return GroupSummary(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        member_count=len(live_ids),
        workspace_ids=live_ids,
    )


def _detail(group: ProjectGroup) -> GroupDetail:
    members: list[GroupMemberRef] = []
    for workspace_id in group.workspace_ids:
        workspace = workspace_repository.get(workspace_id)
        if workspace is None:
            continue
        members.append(
            GroupMemberRef(
                workspace_id=workspace_id,
                name=workspace.name,
                project_path=workspace.project_path,
            )
        )
    return GroupDetail(**_summary(group).model_dump(), members=members)


# --- CRUD ---


@router.get("", response_model=GroupListResponse)
def list_groups() -> GroupListResponse:
    return GroupListResponse(groups=[_summary(g) for g in _manage().list()])


@router.post("", response_model=GroupDetail, status_code=status.HTTP_201_CREATED)
def create_group(request: CreateGroupRequest) -> GroupDetail:
    try:
        group = _manage().create(request.name, request.workspace_ids)
    except ProjectGroupValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _detail(group)


@router.get("/{group_id}", response_model=GroupDetail)
def get_group(group_id: str) -> GroupDetail:
    try:
        return _detail(_manage().get(group_id))
    except ProjectGroupNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.patch("/{group_id}", response_model=GroupDetail)
def update_group(group_id: str, request: UpdateGroupRequest) -> GroupDetail:
    manage = _manage()
    try:
        if request.name is not None:
            manage.rename(group_id, request.name)
        if request.workspace_ids is not None:
            manage.set_members(group_id, request.workspace_ids)
        return _detail(manage.get(group_id))
    except ProjectGroupNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ProjectGroupValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: str) -> None:
    _manage().delete(group_id)


@router.post("/{group_id}/members", response_model=GroupDetail)
def add_member(group_id: str, request: AddMemberRequest) -> GroupDetail:
    try:
        group = _manage().add_member(group_id, request.workspace_id)
    except ProjectGroupNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _detail(group)


@router.delete("/{group_id}/members/{workspace_id}", response_model=GroupDetail)
def remove_member(group_id: str, workspace_id: str) -> GroupDetail:
    try:
        group = _manage().remove_member(group_id, workspace_id)
    except ProjectGroupNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _detail(group)


# --- Overview (Home + Intelligence) ---


class GroupMemberRisk(BaseModel):
    workspace_id: str
    workspace_name: str
    severity: str
    # The softened word ("Worth a close look"), so the group speaks the same language
    # as the single project rather than shouting HIGH at the same fact.
    attention: str = ""
    title: str
    explanation: str = ""
    recommendation: str | None = None
    category: str = ""
    source_file: str | None = None


class GroupMemberOverview(BaseModel):
    workspace_id: str
    name: str
    project_path: str
    built: bool
    indexed: bool
    description: str
    technology_chips: list[str]
    counts: dict[str, int]
    environments: list[str]
    risk_counts: dict[str, int]
    is_repo: bool
    branch: str | None
    total_commits: int
    contributors_count: int
    commits_last_7_days: int
    last_commit_subject: str | None


class GroupOverviewResponse(BaseModel):
    group_id: str
    name: str
    member_count: int
    totals: dict[str, int]
    environments: list[str]
    technologies: list[str]
    risks: list[GroupMemberRisk]
    members: list[GroupMemberOverview]


def _overview_response(overview: GroupOverview) -> GroupOverviewResponse:
    return GroupOverviewResponse(
        group_id=overview.group_id,
        name=overview.name,
        member_count=overview.member_count,
        totals=overview.totals,
        environments=overview.environments,
        technologies=overview.technologies,
        risks=[GroupMemberRisk(**vars(r)) for r in overview.risks],
        members=[GroupMemberOverview(**vars(m)) for m in overview.members],
    )


@router.get("/{group_id}/overview", response_model=GroupOverviewResponse)
def group_overview(group_id: str) -> GroupOverviewResponse:
    use_case = BuildGroupOverviewUseCase(
        group_repository=project_group_repository,
        workspace_repository=workspace_repository,
        project_graph_repository=project_graph_repository,
        git_history=git_history,
        index_status_repository=index_status_repository,
    )
    try:
        return _overview_response(use_case.execute(group_id))
    except BuildGroupOverviewNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


# --- Group-level memory + handbook ---


def _memory_dict(item) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "text": item.text,
        "source": item.source,
        "created_at": item.created_at,
        "pinned": item.pinned,
    }


class AddGroupMemoryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    kind: str = MemoryKind.NOTE
    pinned: bool = False


class PinGroupMemoryRequest(BaseModel):
    pinned: bool


@router.get("/{group_id}/memory")
def list_group_memory(group_id: str) -> dict:
    """All durable notes for the group (newest first)."""
    items = ListMemoryUseCase(project_memory_repository).execute(group_id)
    return {"items": [_memory_dict(i) for i in items]}


@router.post("/{group_id}/memory")
def add_group_memory(group_id: str, request: AddGroupMemoryRequest) -> dict:
    try:
        item = AddMemoryUseCase(project_memory_repository).execute(
            AddMemoryInput(
                workspace_id=group_id,
                text=request.text,
                kind=request.kind,
                pinned=request.pinned,
            )
        )
    except AddMemoryValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _memory_dict(item)


@router.delete("/{group_id}/memory/{item_id}")
def delete_group_memory(group_id: str, item_id: str) -> dict:
    DeleteMemoryUseCase(project_memory_repository).execute(group_id, item_id)
    return {"deleted": True}


@router.post("/{group_id}/memory/{item_id}/pin")
def pin_group_memory(group_id: str, item_id: str, request: PinGroupMemoryRequest) -> dict:
    SetMemoryPinnedUseCase(project_memory_repository).execute(group_id, item_id, request.pinned)
    return {"pinned": request.pinned}


@router.post("/{group_id}/handbook")
def build_group_handbook_endpoint(group_id: str) -> dict:
    """(Re)generate the deterministic group handbook from the aggregated overview."""
    use_case = BuildGroupHandbookUseCase(
        BuildGroupOverviewUseCase(
            group_repository=project_group_repository,
            workspace_repository=workspace_repository,
            project_graph_repository=project_graph_repository,
            git_history=git_history,
            index_status_repository=index_status_repository,
        ),
        project_memory_repository,
    )
    try:
        text = use_case.execute(group_id)
    except BuildGroupHandbookNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return {"handbook": text}


@router.get("/{group_id}/handbook")
def get_group_handbook(group_id: str) -> dict:
    items = ListMemoryUseCase(project_memory_repository).execute(group_id)
    handbook = next((i for i in items if i.kind == MemoryKind.HANDBOOK), None)
    if handbook is None:
        return {"has_handbook": False}
    return {"has_handbook": True, "handbook": handbook.text, "created_at": handbook.created_at}


# --- Ask across the group ---


class GroupAskRequest(BaseModel):
    question: str
    limit: int = 6
    per_repo_cap: int = 3
    llm_provider: str | None = None
    llm_model: str | None = None
    temperature: float | None = None
    think: bool | None = None
    # The thread this question belongs to. Omit it to start a new one — the first
    # question creates the conversation, exactly as a single project's does.
    conversation_id: str | None = None
    answer_mode: str | None = None


class GroupAskSource(BaseModel):
    workspace_id: str
    workspace_name: str
    chunk_id: str
    source_path: str
    score: float
    preview: str


class GroupAskContribution(BaseModel):
    workspace_id: str
    workspace_name: str
    indexed: bool
    chunks_used: int


class GroupAskResponse(BaseModel):
    group_id: str
    conversation_id: str | None = None
    question: str
    answer: str
    sources: list[GroupAskSource]
    contributions: list[GroupAskContribution]
    used_context_chunks: int
    llm_provider: str
    llm_model: str | None
    memory_used: int
    facts_used: int
    diagnostic_code: str | None
    quality_warnings: list[RagQualityWarningResponse] = []
    usage: LLMUsageMetricsResponse | None = None


def _ask_response(
    answer: GroupQuestionAnswer, conversation_id: str | None = None
) -> GroupAskResponse:
    return GroupAskResponse(
        group_id=answer.group_id,
        conversation_id=conversation_id,
        question=answer.question,
        answer=answer.answer,
        sources=[GroupAskSource(**vars(s)) for s in answer.sources],
        contributions=[GroupAskContribution(**vars(c)) for c in answer.contributions],
        used_context_chunks=answer.used_context_chunks,
        llm_provider=answer.llm_provider,
        llm_model=answer.llm_model,
        memory_used=answer.memory_used,
        facts_used=answer.facts_used,
        diagnostic_code=answer.diagnostic_code,
        quality_warnings=[to_rag_quality_warning_response(w) for w in answer.quality_warnings],
        usage=to_llm_usage_metrics_response(answer.usage),
    )


def _build_ask_use_case() -> AskGroupQuestionUseCase:
    return AskGroupQuestionUseCase(
        group_repository=project_group_repository,
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider_factory=llm_provider_factory,
        index_status_repository=index_status_repository,
        index_manifest_repository=index_manifest_repository,
        conversation_repository=conversation_repository,
        project_context_provider=project_context_composer,
        reranker=build_reranker(),
    )


def _ask_input(
    group_id: str, request: GroupAskRequest, conversation_id: str | None = None
) -> AskGroupQuestionInput:
    return AskGroupQuestionInput(
        group_id=group_id,
        question=request.question,
        limit=request.limit,
        per_repo_cap=request.per_repo_cap,
        llm_provider_override=request.llm_provider,
        llm_model_override=request.llm_model,
        temperature=request.temperature,
        think=request.think,
        conversation_id=conversation_id,
        answer_mode=request.answer_mode,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _group_conversation(group_id: str, conversation_id: str | None):
    """The thread this question belongs to, created on the first question. A group
    conversation is scoped by the group id — the same scope its memory uses."""
    conversation = ensure_conversation(
        conversation_repository, group_id, conversation_id, title=None
    )
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


def _persist_group_turn(group_id: str, conversation_id: str, answer: GroupQuestionAnswer) -> None:
    persist_turn(
        conversation_repository,
        group_id,
        conversation_id,
        answer.question,
        answer.answer,
        sources_count=len(answer.sources),
        used_context_chunks=answer.used_context_chunks,
        llm_provider=answer.llm_provider,
        llm_model=answer.llm_model,
        usage=answer.usage,
    )


@router.post("/{group_id}/ask", response_model=GroupAskResponse)
def ask_group(group_id: str, request: GroupAskRequest) -> GroupAskResponse:
    conversation = _group_conversation(group_id, request.conversation_id)
    try:
        answer = _build_ask_use_case().execute(_ask_input(group_id, request, conversation.id))
    except AskGroupQuestionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except AskGroupQuestionValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    _persist_group_turn(group_id, conversation.id, answer)
    return _ask_response(answer, conversation.id)


@router.post("/{group_id}/ask/stream")
def ask_group_stream(group_id: str, request: GroupAskRequest) -> StreamingResponse:
    use_case = _build_ask_use_case()
    conversation = _group_conversation(group_id, request.conversation_id)
    ask_input = _ask_input(group_id, request, conversation.id)

    def event_stream():
        try:
            for event in use_case.execute_stream(ask_input):
                if isinstance(event, GroupAskStreamDelta):
                    yield _sse("token", {"text": event.text})
                elif isinstance(event, GroupAskStreamFinal):
                    _persist_group_turn(group_id, conversation.id, event.answer)
                    yield _sse(
                        "final",
                        _ask_response(event.answer, conversation.id).model_dump(mode="json"),
                    )
        except (AskGroupQuestionNotFoundError, AskGroupQuestionValidationError) as exc:
            # Our own domain errors carry safe, user-facing messages.
            yield _sse("error", {"detail": str(exc)})
        except Exception:  # noqa: BLE001 - surface a failure without leaking internals
            logger.exception("group ask stream failed group_id=%s", group_id)
            yield _sse("error", {"detail": "The request could not be completed. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
