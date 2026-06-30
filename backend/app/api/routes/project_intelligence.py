"""Project Intelligence HTTP API.

Builds and serves the role-neutral project graph and its role-lensed view. The
deterministic facts come from the persisted graph; the optional overview text is
the only LLM-written piece, and it is constrained to those facts.
"""

import contextlib

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    embedding_provider,
    file_system,
    git_history,
    llm_provider_factory,
    project_context_composer,
    project_graph_repository,
    project_memory_repository,
    project_scan_repository,
    project_watch_repository,
    vector_store,
    workspace_repository,
)
from app.core.domain.project_graph import ProjectSnapshotMeta
from app.core.domain.project_intelligence_flow import (
    compare_environments,
    derive_deployment_flow,
)
from app.core.domain.project_intelligence_prompt import (
    build_ask_graph_prompt,
    build_project_intelligence_overview_prompt,
)
from app.core.domain.project_intelligence_view import (
    present_ci,
    present_cloud,
    present_project_graph,
    present_project_intelligence,
    present_references,
)
from app.core.domain.project_memory import MemoryKind
from app.core.domain.role_brief import build_role_brief
from app.core.domain.role_lens import role_lens_for
from app.core.ports.llm_provider_factory import LLMProviderFactoryError
from app.core.use_cases.build_project_graph import (
    BuildProjectGraphInput,
    BuildProjectGraphScanRequiredError,
    BuildProjectGraphUseCase,
    BuildProjectGraphWorkspaceNotFoundError,
)
from app.core.use_cases.build_project_handbook import (
    BuildHandbookGraphRequiredError,
    BuildHandbookInput,
    BuildProjectHandbookUseCase,
)
from app.core.use_cases.investigate_project import (
    InvestigateProjectError,
    InvestigateProjectInput,
    InvestigateProjectUseCase,
    InvestigateProjectWorkspaceNotFoundError,
)
from app.core.use_cases.manage_project_memory import (
    AddMemoryInput,
    AddMemoryUseCase,
    AddMemoryValidationError,
    DeleteMemoryUseCase,
    ListMemoryUseCase,
    SetMemoryPinnedUseCase,
    SetMemoryStaleUseCase,
    SetMemoryStatusUseCase,
)
from app.core.use_cases.record_git_history import (
    RecordGitHistoryInput,
    RecordGitHistoryUseCase,
    RecordGitHistoryWorkspaceNotFoundError,
)
from app.core.use_cases.run_project_watch import (
    RunProjectWatchError,
    RunProjectWatchInput,
    RunProjectWatchUseCase,
)
from app.core.use_cases.scan_workspace_project import (
    ScanWorkspaceProjectInput,
    ScanWorkspaceProjectUseCase,
)
from app.core.use_cases.scan_workspace_project import (
    WorkspaceNotFoundError as ScanWorkspaceNotFoundError,
)

router = APIRouter(prefix="/workspaces", tags=["intelligence"])


def _meta_dict(meta: ProjectSnapshotMeta) -> dict:
    return {
        "id": meta.id,
        "workspace_id": meta.workspace_id,
        "created_at": meta.created_at,
        "entity_count": meta.entity_count,
        "relation_count": meta.relation_count,
        "finding_count": meta.finding_count,
        "analyzers_run": meta.analyzers_run,
        "analyzers_skipped": meta.analyzers_skipped,
        "scan_signature": meta.scan_signature,
    }


def _resolve_role(workspace_id: str, role: str | None) -> str:
    """The view role: explicit override, else the workspace's selected assistant
    mode (chosen at workspace creation), else developer."""
    if role:
        return role
    workspace = workspace_repository.get(workspace_id)
    return (getattr(workspace, "assistant_mode", None) if workspace else None) or "developer"


@router.post("/{workspace_id}/intelligence/build")
def build_project_intelligence(workspace_id: str) -> dict:
    """Build (or rebuild) the project graph. Runs only on this explicit request."""
    use_case = BuildProjectGraphUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
        project_graph_repository=project_graph_repository,
    )
    try:
        meta = use_case.execute(BuildProjectGraphInput(workspace_id=workspace_id))
    except BuildProjectGraphWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuildProjectGraphScanRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"built": True, "snapshot": _meta_dict(meta)}


@router.get("/{workspace_id}/intelligence")
def get_project_intelligence(workspace_id: str, role: str | None = None) -> dict:
    """Latest project graph, projected through the role lens. ``built: false`` when
    the project map has not been built yet."""
    graph = project_graph_repository.get_latest_graph(workspace_id)
    meta = project_graph_repository.get_latest_snapshot_meta(workspace_id)
    if graph is None or meta is None:
        return {"built": False}
    resolved_role = _resolve_role(workspace_id, role)
    lens = role_lens_for(resolved_role)
    view = present_project_intelligence(graph, lens)
    return {
        "built": True,
        "role": resolved_role,
        "snapshot": _meta_dict(meta),
        "view": view,
        "brief": build_role_brief(graph, lens).as_dict(),
        "graph": present_project_graph(graph),
        "flow": derive_deployment_flow(graph),
        "environment_comparison": compare_environments(graph),
        "cloud": present_cloud(graph),
        "references": present_references(graph),
        "ci": present_ci(graph),
    }


@router.get("/{workspace_id}/intelligence/overview-text")
def get_project_intelligence_overview_text(workspace_id: str, role: str | None = None) -> dict:
    """A short plain-language overview written by the local model — constrained to
    the graph facts. Optional; the deterministic sections work without it."""
    graph = project_graph_repository.get_latest_graph(workspace_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Build the project map first.",
        )
    resolved_role = _resolve_role(workspace_id, role)
    lens = role_lens_for(resolved_role)
    view = present_project_intelligence(graph, lens)
    prompt = build_project_intelligence_overview_prompt(view, lens.label)
    try:
        provider = llm_provider_factory.create(provider=None, model=None)
        text = provider.generate(prompt)
    except (LLMProviderFactoryError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The local model could not generate an overview: {exc}",
        ) from exc
    return {"overview": text, "role": resolved_role}


def _watch_rebuild(workspace_id: str) -> ProjectSnapshotMeta:
    """Re-scan the project from disk, then rebuild the graph — so the watcher
    compares against the current files, not a stale scan."""
    ScanWorkspaceProjectUseCase(workspace_repository, file_system, project_scan_repository).execute(
        ScanWorkspaceProjectInput(workspace_id=workspace_id)
    )
    return BuildProjectGraphUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        file_system=file_system,
        project_graph_repository=project_graph_repository,
    ).execute(BuildProjectGraphInput(workspace_id=workspace_id))


def _watch_git_brief(workspace_id: str, since_commit: str | None):
    """A read-only git brief for the workspace's project folder: what landed
    since the commit recorded at the last check."""
    from app.core.domain.git_change_brief import GitChangeBrief

    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        return GitChangeBrief(comparable=False, head=None, commit_count=0)
    return git_history.change_brief(workspace.project_path, since_commit)


@router.post("/{workspace_id}/intelligence/watch")
def run_project_watch(workspace_id: str) -> dict:
    """Run a watcher check: re-scan, rebuild the graph, and report what changed
    since the previous snapshot (graph + a human git brief). Persists the digest."""
    use_case = RunProjectWatchUseCase(
        project_graph_repository=project_graph_repository,
        watch_repository=project_watch_repository,
        build_graph=_watch_rebuild,
        git_brief_provider=_watch_git_brief,
    )
    try:
        digest = use_case.execute(RunProjectWatchInput(workspace_id=workspace_id))
    except (BuildProjectGraphWorkspaceNotFoundError, ScanWorkspaceNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (BuildProjectGraphScanRequiredError, RunProjectWatchError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    # Keep the cheap git-only journal cursor in step with the full check, so the
    # next git-only record doesn't re-list commits this check already logged.
    head = digest.get("git_head") if isinstance(digest, dict) else None
    if head:
        with contextlib.suppress(Exception):
            project_watch_repository.set_history_cursor(workspace_id, head)
    return digest


@router.post("/{workspace_id}/intelligence/watch/history/record")
def record_watch_history(workspace_id: str) -> dict:
    """Record a history entry from git alone - cheap: no rescan, no graph rebuild,
    no re-indexing. Meant to run on app open so the dated journal fills itself."""
    use_case = RecordGitHistoryUseCase(
        workspace_repository=workspace_repository,
        watch_repository=project_watch_repository,
        git_brief_provider=_watch_git_brief,
        project_memory_repository=project_memory_repository,
    )
    try:
        return use_case.execute(RecordGitHistoryInput(workspace_id=workspace_id))
    except RecordGitHistoryWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{workspace_id}/intelligence/watch")
def get_project_watch(workspace_id: str) -> dict:
    """The most recent watcher digest, or ``has_digest: false`` if none yet."""
    digest = project_watch_repository.get_latest_digest(workspace_id)
    if digest is None:
        return {"has_digest": False}
    return {"has_digest": True, "digest": digest}


@router.post("/{workspace_id}/intelligence/watch/summary")
def summarize_project_watch(workspace_id: str) -> dict:
    """A one-tap plain-language summary of the commits in the latest digest, written
    by the local model. Grounded only in the commit subjects already stored in the
    digest — no extra git query — and budgeted to fit the answer window."""
    from app.config.settings import get_settings
    from app.core.domain.git_change_brief import (
        GitChangeBrief,
        build_change_summary_prompt,
    )

    digest = project_watch_repository.get_latest_digest(workspace_id)
    if digest is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run a check first — there is nothing to summarise yet.",
        )
    git_brief = digest.get("git_brief") or {}
    subjects = [s for s in (git_brief.get("commit_subjects") or []) if s]
    commit_count = int(git_brief.get("commit_count") or 0)
    if commit_count <= 0 or not subjects:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No new commits to summarise since the last check.",
        )

    brief = GitChangeBrief(
        comparable=True,
        head=digest.get("git_head"),
        commit_count=commit_count,
        authors=list(git_brief.get("authors") or []),
        commit_subjects=subjects,
    )
    prompt = build_change_summary_prompt(
        brief,
        max_context_tokens=get_settings().LLAMA_SERVER_LLM_CONTEXT_SIZE,
    )
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No new commits to summarise since the last check.",
        )
    try:
        provider = llm_provider_factory.create(provider=None, model=None)
        summary = provider.generate(prompt)
    except (LLMProviderFactoryError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The local model could not summarise the changes: {exc}",
        ) from exc
    clean = summary.strip()
    # Persist the one-tap summary onto the latest history entry so it survives in
    # the timeline instead of disappearing when the view is left (best-effort).
    with contextlib.suppress(Exception):
        project_watch_repository.set_latest_history_summary(workspace_id, clean)
    return {"summary": clean, "commit_count": commit_count}


@router.get("/{workspace_id}/intelligence/watch/history")
def get_project_watch_history(workspace_id: str) -> dict:
    """The change-history timeline: every check that found changes, newest first,
    with its commit subjects and any saved one-tap summary."""
    entries = project_watch_repository.list_history(workspace_id, limit=50)
    return {"entries": entries}


def _memory_dict(item) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "text": item.text,
        "source": item.source,
        "created_at": item.created_at,
        "pinned": item.pinned,
        "confidence": getattr(item, "confidence", 1.0),
        "status": getattr(item, "status", "active"),
        "updated_at": getattr(item, "updated_at", None),
        "stale": getattr(item, "stale", False),
    }


@router.get("/{workspace_id}/memory")
def list_project_memory(workspace_id: str) -> dict:
    """All durable project-memory items (newest first)."""
    items = ListMemoryUseCase(project_memory_repository).execute(workspace_id)
    return {"items": [_memory_dict(i) for i in items]}


class AddMemoryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    kind: str = MemoryKind.NOTE
    pinned: bool = False


@router.post("/{workspace_id}/memory")
def add_project_memory(workspace_id: str, request: AddMemoryRequest) -> dict:
    """Record a note / decision / correction the team wants remembered."""
    try:
        item = AddMemoryUseCase(project_memory_repository).execute(
            AddMemoryInput(
                workspace_id=workspace_id,
                text=request.text,
                kind=request.kind,
                pinned=request.pinned,
            )
        )
    except AddMemoryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _memory_dict(item)


@router.delete("/{workspace_id}/memory/{item_id}")
def delete_project_memory(workspace_id: str, item_id: str) -> dict:
    DeleteMemoryUseCase(project_memory_repository).execute(workspace_id, item_id)
    return {"deleted": True}


class PinMemoryRequest(BaseModel):
    pinned: bool


@router.post("/{workspace_id}/memory/{item_id}/pin")
def pin_project_memory(workspace_id: str, item_id: str, request: PinMemoryRequest) -> dict:
    SetMemoryPinnedUseCase(project_memory_repository).execute(workspace_id, item_id, request.pinned)
    return {"pinned": request.pinned}


class MemoryStatusRequest(BaseModel):
    status: str


@router.post("/{workspace_id}/memory/{item_id}/status")
def set_project_memory_status(
    workspace_id: str, item_id: str, request: MemoryStatusRequest
) -> dict:
    """Mark a memory item active or obsolete. Obsolete items stay listed but are
    never fed into prompts, so stale knowledge can't poison answers."""
    try:
        SetMemoryStatusUseCase(project_memory_repository).execute(
            workspace_id, item_id, request.status
        )
    except AddMemoryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": request.status}


class MemoryStaleRequest(BaseModel):
    stale: bool


@router.post("/{workspace_id}/memory/{item_id}/stale")
def set_project_memory_stale(workspace_id: str, item_id: str, request: MemoryStaleRequest) -> dict:
    """Set/clear a memory's stale flag. Clearing it is the user's "still correct"
    confirmation after a file the memory references changed."""
    SetMemoryStaleUseCase(project_memory_repository).execute(workspace_id, item_id, request.stale)
    return {"stale": request.stale}


@router.post("/{workspace_id}/handbook")
def build_project_handbook(workspace_id: str) -> dict:
    """(Re)generate the deterministic project handbook from the latest map."""
    try:
        text = BuildProjectHandbookUseCase(
            project_graph_repository, project_memory_repository
        ).execute(BuildHandbookInput(workspace_id=workspace_id))
    except BuildHandbookGraphRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"handbook": text}


@router.get("/{workspace_id}/handbook")
def get_project_handbook(workspace_id: str) -> dict:
    """The stored handbook text, or ``has_handbook: false`` if none yet."""
    items = ListMemoryUseCase(project_memory_repository).execute(workspace_id)
    handbook = next((i for i in items if i.kind == MemoryKind.HANDBOOK), None)
    if handbook is None:
        return {"has_handbook": False}
    return {"has_handbook": True, "handbook": handbook.text, "created_at": handbook.created_at}


class InvestigateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    role: str | None = None


@router.post("/{workspace_id}/intelligence/investigate")
def investigate_project(workspace_id: str, request: InvestigateRequest) -> dict:
    """Read-only multi-step investigation: the local model uses read-only tools
    (code search, file read, graph query, file listing) to answer a question, and
    returns its transparent step trace plus the sources it consulted."""
    use_case = InvestigateProjectUseCase(
        workspace_repository=workspace_repository,
        llm_provider_factory=llm_provider_factory,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        file_system=file_system,
        project_graph_repository=project_graph_repository,
        project_scan_repository=project_scan_repository,
        git_history=git_history,
        memory_repository=project_memory_repository,
        context_provider=project_context_composer,
    )
    try:
        result = use_case.execute(
            InvestigateProjectInput(
                workspace_id=workspace_id,
                question=request.question.strip(),
                role=request.role,
            )
        )
    except InvestigateProjectWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvestigateProjectError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The local model could not run the investigation: {exc}",
        ) from exc
    return {
        "answer": result.answer,
        "steps": [
            {
                "thought": s.thought,
                "tool": s.tool,
                "tool_input": s.tool_input,
                "observation": s.observation,
            }
            for s in result.steps
        ],
        "sources": result.sources,
        "used_steps": result.used_steps,
        "stopped_reason": result.stopped_reason,
        "context_used": {
            "memory": result.memory_used,
            "facts": result.facts_used,
        },
    }


class AskProjectIntelligenceRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    role: str | None = None


@router.post("/{workspace_id}/intelligence/ask")
def ask_project_intelligence(workspace_id: str, request: AskProjectIntelligenceRequest) -> dict:
    """Answer a free-text question about the project using ONLY the graph facts.
    The local model is instructed to say so when the answer is not in the files."""
    graph = project_graph_repository.get_latest_graph(workspace_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Build the project map first.",
        )
    resolved_role = _resolve_role(workspace_id, request.role)
    lens = role_lens_for(resolved_role)
    view = present_project_intelligence(graph, lens)
    prompt = build_ask_graph_prompt(view, lens.label, request.question.strip())
    try:
        provider = llm_provider_factory.create(provider=None, model=None)
        answer = provider.generate(prompt)
    except (LLMProviderFactoryError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The local model could not answer: {exc}",
        ) from exc
    return {"answer": answer, "role": resolved_role}
