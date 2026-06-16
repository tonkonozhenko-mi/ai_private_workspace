from pydantic import BaseModel, Field

from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.domain.skill import SkillMatch


class FileSelectionRulesRequest(BaseModel):
    profile: str = "balanced"
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)


class ScanWorkspaceProjectRequest(BaseModel):
    file_rules: FileSelectionRulesRequest | None = None




class FileSelectionPreviewItemResponse(BaseModel):
    path: str
    detected_type: str
    size_bytes: int
    decision: str
    reason: str
    matched_rule: str | None = None


class FileSelectionPreviewResponse(BaseModel):
    workspace_id: str
    project_path: str
    profile: str
    total_files: int
    included_files_count: int
    excluded_files_count: int
    skipped_files_count: int
    include_rules_count: int
    exclude_rules_count: int
    included_samples: list[FileSelectionPreviewItemResponse]
    excluded_samples: list[FileSelectionPreviewItemResponse]


def to_file_selection_preview_response(result) -> FileSelectionPreviewResponse:
    return FileSelectionPreviewResponse(
        workspace_id=result.workspace_id,
        project_path=result.project_path,
        profile=result.profile,
        total_files=result.total_files,
        included_files_count=result.included_files_count,
        excluded_files_count=result.excluded_files_count,
        skipped_files_count=result.skipped_files_count,
        include_rules_count=result.include_rules_count,
        exclude_rules_count=result.exclude_rules_count,
        included_samples=[
            FileSelectionPreviewItemResponse(
                path=item.path,
                detected_type=item.detected_type,
                size_bytes=item.size_bytes,
                decision=item.decision,
                reason=item.reason,
                matched_rule=item.matched_rule,
            )
            for item in result.included_samples
        ],
        excluded_samples=[
            FileSelectionPreviewItemResponse(
                path=item.path,
                detected_type=item.detected_type,
                size_bytes=item.size_bytes,
                decision=item.decision,
                reason=item.reason,
                matched_rule=item.matched_rule,
            )
            for item in result.excluded_samples
        ],
    )


class ScanChangesResponse(BaseModel):
    has_baseline: bool
    changed: bool
    added_count: int
    removed_count: int
    modified_count: int
    current_file_count: int
    previous_file_count: int


def to_scan_changes_response(result) -> ScanChangesResponse:
    return ScanChangesResponse(
        has_baseline=result.has_baseline,
        changed=result.changed,
        added_count=result.added_count,
        removed_count=result.removed_count,
        modified_count=result.modified_count,
        current_file_count=result.current_file_count,
        previous_file_count=result.previous_file_count,
    )


class ProjectFileResponse(BaseModel):
    path: str
    extension: str | None
    size_bytes: int
    detected_type: str
    modified_at: float | None = None


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
        modified_at=project_file.modified_at,
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
