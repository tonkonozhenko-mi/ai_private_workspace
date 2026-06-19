"""Project Intelligence HTTP API.

Builds and serves the role-neutral project graph and its role-lensed view. The
deterministic facts come from the persisted graph; the optional overview text is
the only LLM-written piece, and it is constrained to those facts.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    file_system,
    llm_provider_factory,
    project_graph_repository,
    project_scan_repository,
    workspace_repository,
)
from app.core.domain.project_graph import ProjectSnapshotMeta
from app.core.domain.project_intelligence_prompt import (
    build_project_intelligence_overview_prompt,
)
from app.core.domain.project_intelligence_view import (
    present_project_graph,
    present_project_intelligence,
)
from app.core.domain.role_lens import role_lens_for
from app.core.ports.llm_provider_factory import LLMProviderFactoryError
from app.core.use_cases.build_project_graph import (
    BuildProjectGraphInput,
    BuildProjectGraphScanRequiredError,
    BuildProjectGraphUseCase,
    BuildProjectGraphWorkspaceNotFoundError,
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
    view = present_project_intelligence(graph, role_lens_for(resolved_role))
    return {
        "built": True,
        "role": resolved_role,
        "snapshot": _meta_dict(meta),
        "view": view,
        "graph": present_project_graph(graph),
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
