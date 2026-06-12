from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.api.project_scan_schemas import ProjectScanResponse, to_project_scan_response
from app.core.use_cases.scan_project import (
    ProjectScanError,
    ScanProjectInput,
    ScanProjectUseCase,
)


router = APIRouter(prefix="/projects", tags=["projects"])

file_system = LocalFileSystem()


class ScanProjectRequest(BaseModel):
    project_path: str = Field(..., min_length=1)


@router.post("/scan", response_model=ProjectScanResponse)
def scan_project(request: ScanProjectRequest) -> ProjectScanResponse:
    use_case = ScanProjectUseCase(file_system)

    try:
        result = use_case.execute(ScanProjectInput(project_path=request.project_path))
    except ProjectScanError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_project_scan_response(result)
