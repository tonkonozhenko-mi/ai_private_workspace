from pydantic import BaseModel, Field

from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.domain.skill import SkillMatch


class FileSelectionRulesRequest(BaseModel):
    profile: str = "balanced"
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)


class ScanWorkspaceProjectRequest(BaseModel):
    file_rules: FileSelectionRulesRequest | None = None


class ProjectFileResponse(BaseModel):
    path: str
    extension: str | None
    size_bytes: int
    detected_type: str


class DetectedSkillResponse(BaseModel):
    name: str
    category: str
    confidence: str
    evidence: list[str]


class ProjectScanResponse(BaseModel):
    project_path: str
    total_files: int
    scanned_files: int
    skipped_files: int
    total_size_bytes: int
    detected_skills: list[DetectedSkillResponse]
    files: list[ProjectFileResponse]


def to_project_file_response(project_file: ProjectFile) -> ProjectFileResponse:
    return ProjectFileResponse(
        path=project_file.path,
        extension=project_file.extension,
        size_bytes=project_file.size_bytes,
        detected_type=project_file.detected_type,
    )


def to_detected_skill_response(skill: SkillMatch) -> DetectedSkillResponse:
    return DetectedSkillResponse(
        name=skill.name,
        category=skill.category,
        confidence=skill.confidence,
        evidence=skill.evidence,
    )


def to_project_scan_response(result: ProjectScanResult) -> ProjectScanResponse:
    return ProjectScanResponse(
        project_path=result.project_path,
        total_files=result.total_files,
        scanned_files=result.scanned_files,
        skipped_files=result.skipped_files,
        total_size_bytes=result.total_size_bytes,
        detected_skills=[
            to_detected_skill_response(skill) for skill in result.detected_skills
        ],
        files=[to_project_file_response(project_file) for project_file in result.files],
    )
