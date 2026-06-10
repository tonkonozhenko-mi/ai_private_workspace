from dataclasses import dataclass
from fnmatch import fnmatch

from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.skill_registry import SkillRegistry
from app.core.ports.file_system import FileSystemPort


@dataclass(frozen=True)
class ScanProjectInput:
    project_path: str
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()


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

        discovered_files = self.file_system.list_files(request.project_path)
        files = self._apply_file_rules(
            files=list(discovered_files),
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
        )
        detected_skills = self.skill_registry.detect_skills(files)
        base_skipped_files = getattr(discovered_files, "skipped_files", 0)
        excluded_files = len(discovered_files) - len(files)
        skipped_files = base_skipped_files + excluded_files
        total_files = getattr(
            discovered_files,
            "total_files",
            len(discovered_files) + base_skipped_files,
        )
        total_size_bytes = sum(project_file.size_bytes for project_file in files)

        return ProjectScanResult(
            project_path=request.project_path,
            total_files=total_files,
            scanned_files=len(files),
            skipped_files=skipped_files,
            total_size_bytes=total_size_bytes,
            detected_skills=detected_skills,
            files=list(files),
        )

    def _apply_file_rules(
        self,
        files: list,
        include_patterns: tuple[str, ...],
        exclude_patterns: tuple[str, ...],
    ) -> list:
        include_rules = self._normalize_patterns(include_patterns)
        exclude_rules = self._normalize_patterns(exclude_patterns)

        return [
            project_file
            for project_file in files
            if self._is_included(project_file.path, include_rules)
            and not self._is_excluded(project_file.path, exclude_rules)
        ]

    @staticmethod
    def _normalize_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(pattern.strip() for pattern in patterns if pattern.strip())

    @staticmethod
    def _is_included(path: str, include_patterns: tuple[str, ...]) -> bool:
        if not include_patterns:
            return True
        return any(_matches_path(path, pattern) for pattern in include_patterns)

    @staticmethod
    def _is_excluded(path: str, exclude_patterns: tuple[str, ...]) -> bool:
        return any(_matches_path(path, pattern) for pattern in exclude_patterns)


def _matches_path(path: str, pattern: str) -> bool:
    normalized_path = path.lstrip("/")
    normalized_pattern = pattern.lstrip("/")
    if fnmatch(normalized_path, normalized_pattern):
        return True
    if normalized_pattern.endswith("/**"):
        prefix = normalized_pattern[:-3].rstrip("/")
        return normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
    return False
