from dataclasses import dataclass
from typing import Callable
from fnmatch import fnmatch

from app.core.domain.gitignore_matcher import (
    GitignoreMatcher,
    discover_gitignore_relative_paths,
)
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.skill_registry import SkillRegistry
from app.core.ports.file_system import FileSystemPort


@dataclass(frozen=True)
class ScanProjectInput:
    project_path: str
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    respect_gitignore: bool = True
    cancellation_check: Callable[[], bool] | None = None
    progress_callback: Callable[[int, int, str], None] | None = None


class ProjectScanError(ValueError):
    pass


class ProjectScanCancelledError(RuntimeError):
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

        self._checkpoint(request.cancellation_check)
        if request.progress_callback is not None:
            request.progress_callback(0, 1, "Discovering project files...")
        discovered_files = self.file_system.list_files(request.project_path)
        self._checkpoint(request.cancellation_check)
        gitignore_matcher = self._build_gitignore_matcher(
            project_path=request.project_path,
            discovered_files=list(discovered_files),
            respect_gitignore=request.respect_gitignore,
        )
        files = self._apply_file_rules(
            files=list(discovered_files),
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
            gitignore_matcher=gitignore_matcher,
            cancellation_check=request.cancellation_check,
            progress_callback=request.progress_callback,
        )
        if request.progress_callback is not None:
            request.progress_callback(len(files), len(files) or 1, "Detecting project technologies...")
        self._checkpoint(request.cancellation_check)
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

    def _build_gitignore_matcher(
        self,
        project_path: str,
        discovered_files: list,
        respect_gitignore: bool,
    ) -> GitignoreMatcher:
        if not respect_gitignore:
            return GitignoreMatcher.empty()
        relative_paths = discover_gitignore_relative_paths(
            [project_file.path for project_file in discovered_files]
        )
        if not relative_paths:
            return GitignoreMatcher.empty()
        sources: dict[str, str] = {}
        for relative_path in relative_paths:
            try:
                content = self.file_system.read_text_file(project_path, relative_path)
            except Exception:
                content = ""
            if content:
                sources[relative_path] = content
        return GitignoreMatcher.from_sources(sources)

    def _apply_file_rules(
        self,
        files: list,
        include_patterns: tuple[str, ...],
        exclude_patterns: tuple[str, ...],
        gitignore_matcher: GitignoreMatcher | None = None,
        cancellation_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list:
        include_rules = self._normalize_patterns(include_patterns)
        exclude_rules = self._normalize_patterns(exclude_patterns)
        matcher = gitignore_matcher or GitignoreMatcher.empty()
        selected_files = []
        total = len(files) or 1

        for index, project_file in enumerate(files, start=1):
            self._checkpoint(cancellation_check)
            if (
                self._is_included(project_file.path, include_rules)
                and not self._is_excluded(project_file.path, exclude_rules)
                and not matcher.is_ignored(project_file.path)
            ):
                selected_files.append(project_file)
            if progress_callback is not None:
                progress_callback(index, total, f"Scanning files: {index}/{total}")

        return selected_files

    @staticmethod
    def _checkpoint(cancellation_check: Callable[[], bool] | None) -> None:
        if cancellation_check is not None and cancellation_check():
            raise ProjectScanCancelledError("Project scan cancelled")

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
