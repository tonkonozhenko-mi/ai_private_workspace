from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    agent_workflow_repository,
    mcp_repository,
    model_catalog_registry,
    workspace_repository,
)
from app.api.schemas.agent_workflow_schemas import (
    AgentWorkflowArchiveRequest,
    AgentWorkflowListResponse,
    AgentWorkflowResponse,
    CreateAgentWorkflowRequest,
    UpdateAgentWorkflowStepApprovalRequest,
    UpdateAgentWorkflowStepEvidenceRequest,
    UpdateAgentWorkflowStepRequest,
    to_agent_step_approval_preview_response,
    to_agent_workflow_execution_readiness_response,
    to_agent_workflow_response,
)
from app.core.domain.agent_capability import build_agent_capability, build_agent_planning_preview
from app.core.domain.agent_workflow import (
    archive_agent_workflow,
    build_step_approval_preview,
    build_workflow_execution_readiness,
    create_agent_workflow_from_preview,
    update_workflow_step_approval,
    update_workflow_step_evidence,
    update_workflow_step_status,
)
from app.core.domain.mcp_server import build_mcp_tool_inventory

router = APIRouter(prefix="/workspaces/{workspace_id}/agent-workflows", tags=["agent-workflows"])


@router.get("", response_model=AgentWorkflowListResponse)
def list_agent_workflows(
    workspace_id: str, include_archived: bool = False
) -> AgentWorkflowListResponse:
    _require_workspace(workspace_id)
    workflows = agent_workflow_repository.list_workflows(
        workspace_id, include_archived=include_archived
    )
    return AgentWorkflowListResponse(
        workspace_id=workspace_id,
        items=[to_agent_workflow_response(workflow) for workflow in workflows],
        safety_note="Agent workflows are manual tracking drafts. The app does not execute the listed steps automatically.",
    )


@router.post("", response_model=AgentWorkflowResponse)
def create_agent_workflow(
    workspace_id: str, request: CreateAgentWorkflowRequest
) -> AgentWorkflowResponse:
    _require_workspace(workspace_id)
    capability = _find_capability(request.provider, request.model)
    preview = build_agent_planning_preview(
        goal=request.goal,
        provider=request.provider,
        model=request.model,
        capability=capability,
    )
    workflow = create_agent_workflow_from_preview(
        workspace_id=workspace_id,
        goal=request.goal,
        provider=request.provider,
        model=request.model,
        readiness=preview.readiness,
        agent_mode=preview.agent_mode,
        preview_steps=preview.steps,
        guardrails=preview.guardrails,
        unsupported_actions=preview.unsupported_actions,
        safety_note=preview.safety_note,
    )
    return to_agent_workflow_response(agent_workflow_repository.save_workflow(workflow))


@router.get("/{workflow_id}", response_model=AgentWorkflowResponse)
def get_agent_workflow(workspace_id: str, workflow_id: str) -> AgentWorkflowResponse:
    workflow = _require_workflow(workspace_id, workflow_id)
    return to_agent_workflow_response(workflow)


@router.patch("/{workflow_id}/steps/{step_id}", response_model=AgentWorkflowResponse)
def update_agent_workflow_step(
    workspace_id: str,
    workflow_id: str,
    step_id: str,
    request: UpdateAgentWorkflowStepRequest,
) -> AgentWorkflowResponse:
    workflow = _require_workflow(workspace_id, workflow_id)
    try:
        updated = update_workflow_step_status(
            workflow, step_id=step_id, status=request.status, notes=request.notes
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent workflow step not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_agent_workflow_response(agent_workflow_repository.save_workflow(updated))


@router.post("/{workflow_id}/steps/{step_id}/approval-preview")
def preview_agent_workflow_step_approval(
    workspace_id: str,
    workflow_id: str,
    step_id: str,
):
    workflow = _require_workflow(workspace_id, workflow_id)
    try:
        preview = build_step_approval_preview(workflow, step_id=step_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent workflow step not found"
        ) from exc
    return to_agent_step_approval_preview_response(preview)


@router.patch("/{workflow_id}/steps/{step_id}/approval", response_model=AgentWorkflowResponse)
def update_agent_workflow_step_approval(
    workspace_id: str,
    workflow_id: str,
    step_id: str,
    request: UpdateAgentWorkflowStepApprovalRequest,
) -> AgentWorkflowResponse:
    workflow = _require_workflow(workspace_id, workflow_id)
    try:
        updated = update_workflow_step_approval(
            workflow,
            step_id=step_id,
            approval_status=request.approval_status,
            approval_note=request.approval_note,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent workflow step not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_agent_workflow_response(agent_workflow_repository.save_workflow(updated))


@router.patch("/{workflow_id}/steps/{step_id}/evidence", response_model=AgentWorkflowResponse)
def update_agent_workflow_step_evidence_route(
    workspace_id: str,
    workflow_id: str,
    step_id: str,
    request: UpdateAgentWorkflowStepEvidenceRequest,
) -> AgentWorkflowResponse:
    workflow = _require_workflow(workspace_id, workflow_id)
    try:
        updated = update_workflow_step_evidence(
            workflow,
            step_id=step_id,
            evidence_status=request.evidence_status,
            evidence_summary=request.evidence_summary,
            evidence_sources=request.evidence_sources,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent workflow step not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_agent_workflow_response(agent_workflow_repository.save_workflow(updated))


@router.get("/{workflow_id}/execution-readiness")
def get_agent_workflow_execution_readiness(workspace_id: str, workflow_id: str):
    workflow = _require_workflow(workspace_id, workflow_id)
    inventory = build_mcp_tool_inventory(workspace_id, mcp_repository.list_configs(workspace_id))
    readiness = build_workflow_execution_readiness(workflow, inventory.tools)
    return to_agent_workflow_execution_readiness_response(readiness)


@router.patch("/{workflow_id}/archive", response_model=AgentWorkflowResponse)
def archive_workflow(
    workspace_id: str,
    workflow_id: str,
    request: AgentWorkflowArchiveRequest,
) -> AgentWorkflowResponse:
    workflow = _require_workflow(workspace_id, workflow_id)
    updated = archive_agent_workflow(workflow, archived=request.archived)
    return to_agent_workflow_response(agent_workflow_repository.save_workflow(updated))


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_workflow(workspace_id: str, workflow_id: str) -> None:
    _require_workspace(workspace_id)
    deleted = agent_workflow_repository.delete_workflow(workspace_id, workflow_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent workflow not found"
        )


def _require_workspace(workspace_id: str) -> None:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


def _require_workflow(workspace_id: str, workflow_id: str):
    _require_workspace(workspace_id)
    workflow = agent_workflow_repository.get_workflow(workspace_id, workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent workflow not found"
        )
    return workflow


def _find_capability(provider: str | None, model: str | None):
    if not provider or not model:
        return None
    for catalog_model in model_catalog_registry.list_models():
        if catalog_model.provider == provider and catalog_model.model_name == model:
            return build_agent_capability(catalog_model)
    return None
