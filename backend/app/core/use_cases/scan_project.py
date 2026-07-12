import logging
from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from time import perf_counter

from app.core.domain.folder_access import FolderPermissionError
from app.core.domain.gitignore_matcher import (
    GitignoreMatcher,
    discover_gitignore_relative_paths,
)
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.skill_registry import SkillRegistry
from app.core.ports.file_system import FileSystemPort

logger = logging.getLogger(__name__)


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
        discover_started = perf_counter()

        # Prune gitignored directories during the walk (huge speedup on repos with
        # large ignored trees). Safe because the file-rule filter below drops every
        # gitignored file anyway — so the kept set is identical, only faster. Gated
        # on the same respect_gitignore flag so results never diverge from the filter.
        # The walk is the one step that can take minutes with nothing to show for it —
        # and, on macOS, the one that can block on a permission dialog the person never
        # saw. Report the running count so the UI can tell "big repository" from
        # "waiting for you", and turn an unreadable folder into a clear failure rather
        # than a silently smaller project.
        def _walk_progress(found: int) -> None:
            if request.progress_callback is not None:
                request.progress_callback(found, 0, f"Enumerating files… {found} found")

        try:
            discovered_files = self.file_system.list_files(
                request.project_path,
                respect_gitignore=request.respect_gitignore,
                progress=_walk_progress,
            )
        except FolderPermissionError as exc:
            raise ProjectScanError(str(exc)) from exc
        discover_ms = (perf_counter() - discover_started) * 1000
        self._checkpoint(request.cancellation_check)
        gitignore_started = perf_counter()
        gitignore_matcher = self._build_gitignore_matcher(
            project_path=request.project_path,
            discovered_files=list(discovered_files),
            respect_gitignore=request.respect_gitignore,
        )
        gitignore_ms = (perf_counter() - gitignore_started) * 1000
        filter_started = perf_counter()
        files = self._apply_file_rules(
            files=list(discovered_files),
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
            gitignore_matcher=gitignore_matcher,
            cancellation_check=request.cancellation_check,
            progress_callback=request.progress_callback,
        )
        filter_ms = (perf_counter() - filter_started) * 1000
        if request.progress_callback is not None:
            request.progress_callback(
                len(files), len(files) or 1, "Detecting project technologies..."
            )
        self._checkpoint(request.cancellation_check)
        skills_started = perf_counter()
        detected_skills = self.skill_registry.detect_skills(files)
        skills_ms = (perf_counter() - skills_started) * 1000
        # One summary line so a slow scan can be attributed to a phase without a
        # profiler. "discover" is the file walk + type classification (the
        # "Enumerating files…" window); the rest are the post-walk steps.
        logger.info(
            "scan.phases discover=%.0fms gitignore=%.0fms filter=%.0fms skills=%.0fms "
            "discovered=%d kept=%d",
            discover_ms,
            gitignore_ms,
            filter_ms,
            skills_ms,
            len(discovered_files),
            len(files),
        )
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
