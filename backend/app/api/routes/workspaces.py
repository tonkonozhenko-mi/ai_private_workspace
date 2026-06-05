from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.adapters.memory.in_memory_project_scan_repository import (
    InMemoryProjectScanRepository,
)
from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.adapters.memory.sqlite_project_scan_repository import SQLiteProjectScanRepository
from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.api.project_scan_schemas import ProjectScanResponse, to_project_scan_response
from app.api.schemas.workspace_summary_schemas import (
    WorkspaceSummaryResponse,
    to_workspace_summary_response,
)
from app.config.settings import get_settings
from app.core.domain.workspace import Workspace
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.create_workspace import (
    CreateWorkspaceInput,
    CreateWorkspaceUseCase,
)
from app.core.use_cases.get_workspace_latest_scan import (
    GetWorkspaceLatestScanInput,
    GetWorkspaceLatestScanUseCase,
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


def build_workspace_repository() -> WorkspaceRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryWorkspaceRepository()
    if repository_type == "sqlite":
        return SQLiteWorkspaceRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_scan_repository() -> ProjectScanRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectScanRepository()
    if repository_type == "sqlite":
        return SQLiteProjectScanRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


workspace_repository = build_workspace_repository()
project_scan_repository = build_project_scan_repository()
file_system = LocalFileSystem()


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
    )

    try:
        summary = use_case.execute(GetWorkspaceSummaryInput(workspace_id=workspace_id))
    except WorkspaceSummaryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_summary_response(summary)
