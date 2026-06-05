from dataclasses import dataclass

from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.skill_registry import SkillRegistry
from app.core.ports.file_system import FileSystemPort


@dataclass(frozen=True)
class ScanProjectInput:
    project_path: str


class ProjectScanError(ValueError):
    pass


class ScanProjectUseCase:
    def __init__(
        self,
        file_system: FileSystemPort,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.file_system = file_system
        self.skill_registry = skill_registry or SkillRegistry()

    def execute(self, request: ScanProjectInput) -> ProjectScanResult:
        if not self.file_system.path_exists(request.project_path):
            raise ProjectScanError("Project path does not exist")
        if not self.file_system.is_directory(request.project_path):
            raise ProjectScanError("Project path is not a directory")

        files = self.file_system.list_files(request.project_path)
        detected_skills = self.skill_registry.detect_skills(files)
        skipped_files = getattr(files, "skipped_files", 0)
        total_files = getattr(files, "total_files", len(files) + skipped_files)
        total_size_bytes = getattr(
            files,
            "total_size_bytes",
            sum(project_file.size_bytes for project_file in files),
        )

        return ProjectScanResult(
            project_path=request.project_path,
            total_files=total_files,
            scanned_files=len(files),
            skipped_files=skipped_files,
            total_size_bytes=total_size_bytes,
            detected_skills=detected_skills,
            files=list(files),
        )
