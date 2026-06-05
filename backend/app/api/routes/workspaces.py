from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.config.settings import get_settings
from app.core.domain.workspace import Workspace
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.create_workspace import (
    CreateWorkspaceInput,
    CreateWorkspaceUseCase,
)
from app.core.use_cases.get_workspace import GetWorkspaceUseCase
from app.core.use_cases.list_workspaces import ListWorkspacesUseCase


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def build_workspace_repository() -> WorkspaceRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryWorkspaceRepository()
    if repository_type == "sqlite":
        return SQLiteWorkspaceRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


workspace_repository = build_workspace_repository()


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
