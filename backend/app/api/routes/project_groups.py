"""Project groups HTTP API.

A group treats several workspaces as one project. CRUD + membership here is a thin
wrapper over the manage use case; Ask fans a question across members; Overview
aggregates each member's facts and git into a single group view. Member
workspaces are only referenced — never created or deleted by these endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    embedding_provider,
    git_history,
    index_status_repository,
    llm_provider_factory,
    project_graph_repository,
    project_group_repository,
    vector_store,
    workspace_repository,
)
from app.core.domain.group_overview import GroupOverview
from app.core.domain.group_qa import GroupQuestionAnswer
from app.core.domain.project_group import ProjectGroup
from app.core.use_cases.ask_group_question import (
    AskGroupQuestionInput,
    AskGroupQuestionNotFoundError,
    AskGroupQuestionUseCase,
    AskGroupQuestionValidationError,
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

router = APIRouter(prefix="/workspace-groups", tags=["workspace-groups"])


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


def _summary(group: ProjectGroup) -> GroupSummary:
    return GroupSummary(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        member_count=group.member_count,
        workspace_ids=list(group.workspace_ids),
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
    title: str


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


# --- Ask across the group ---


class GroupAskRequest(BaseModel):
    question: str
    limit: int = 6
    per_repo_cap: int = 3
    llm_provider: str | None = None
    llm_model: str | None = None


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
    question: str
    answer: str
    sources: list[GroupAskSource]
    contributions: list[GroupAskContribution]
    used_context_chunks: int
    llm_provider: str
    llm_model: str | None
    diagnostic_code: str | None


def _ask_response(answer: GroupQuestionAnswer) -> GroupAskResponse:
    return GroupAskResponse(
        group_id=answer.group_id,
        question=answer.question,
        answer=answer.answer,
        sources=[GroupAskSource(**vars(s)) for s in answer.sources],
        contributions=[GroupAskContribution(**vars(c)) for c in answer.contributions],
        used_context_chunks=answer.used_context_chunks,
        llm_provider=answer.llm_provider,
        llm_model=answer.llm_model,
        diagnostic_code=answer.diagnostic_code,
    )


@router.post("/{group_id}/ask", response_model=GroupAskResponse)
def ask_group(group_id: str, request: GroupAskRequest) -> GroupAskResponse:
    use_case = AskGroupQuestionUseCase(
        group_repository=project_group_repository,
        workspace_repository=workspace_repository,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider_factory=llm_provider_factory,
        index_status_repository=index_status_repository,
    )
    try:
        answer = use_case.execute(
            AskGroupQuestionInput(
                group_id=group_id,
                question=request.question,
                limit=request.limit,
                per_repo_cap=request.per_repo_cap,
                llm_provider_override=request.llm_provider,
                llm_model_override=request.llm_model,
            )
        )
    except AskGroupQuestionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except AskGroupQuestionValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _ask_response(answer)
