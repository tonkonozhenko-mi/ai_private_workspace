from dataclasses import dataclass
from fnmatch import fnmatch

from app.core.domain.gitignore_matcher import (
    GitignoreMatcher,
    discover_gitignore_relative_paths,
)
from app.core.ports.file_system import FileSystemPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class PreviewWorkspaceFileSelectionInput:
    workspace_id: str
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    file_rules_profile: str | None = None
    respect_gitignore: bool = True
    sample_limit: int = 8


@dataclass(frozen=True)
class FileSelectionPreviewItem:
    path: str
    detected_type: str
    size_bytes: int
    decision: str
    reason: str
    matched_rule: str | None = None


@dataclass(frozen=True)
class FileSelectionPreviewResult:
    workspace_id: str
    project_path: str
    profile: str
    total_files: int
    included_files_count: int
    excluded_files_count: int
    skipped_files_count: int
    include_rules_count: int
    exclude_rules_count: int
    included_samples: list[FileSelectionPreviewItem]
    excluded_samples: list[FileSelectionPreviewItem]


class PreviewWorkspaceFileSelectionWorkspaceNotFoundError(ValueError):
    pass


class PreviewWorkspaceFileSelectionError(ValueError):
    pass


class PreviewWorkspaceFileSelectionUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.file_system = file_system

    def execute(self, request: PreviewWorkspaceFileSelectionInput) -> FileSelectionPreviewResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise PreviewWorkspaceFileSelectionWorkspaceNotFoundError("Workspace not found")
        if not self.file_system.path_exists(workspace.project_path):
            raise PreviewWorkspaceFileSelectionError("Project path does not exist")
        if not self.file_system.is_directory(workspace.project_path):
            raise PreviewWorkspaceFileSelectionError("Project path is not a directory")

        discovered_files = self.file_system.list_files(workspace.project_path)
        include_rules = _normalize_patterns(request.include_patterns)
        exclude_rules = _normalize_patterns(request.exclude_patterns)
        gitignore_matcher = self._build_gitignore_matcher(
            project_path=workspace.project_path,
            discovered_files=list(discovered_files),
            respect_gitignore=request.respect_gitignore,
        )
        included_samples: list[FileSelectionPreviewItem] = []
        excluded_samples: list[FileSelectionPreviewItem] = []
        included_count = 0
        excluded_count = 0

        for project_file in discovered_files:
            decision = _classify_file(
                project_file.path, include_rules, exclude_rules, gitignore_matcher
            )
            item = FileSelectionPreviewItem(
                path=project_file.path,
                detected_type=project_file.detected_type,
                size_bytes=project_file.size_bytes,
                decision=decision.decision,
                reason=decision.reason,
                matched_rule=decision.matched_rule,
            )
            if decision.decision == "included":
                included_count += 1
                if len(included_samples) < request.sample_limit:
                    included_samples.append(item)
            else:
                excluded_count += 1
                if len(excluded_samples) < request.sample_limit:
                    excluded_samples.append(item)

        base_skipped_files = getattr(discovered_files, "skipped_files", 0)
        total_files = getattr(
            discovered_files,
            "total_files",
            len(discovered_files) + base_skipped_files,
        )

        return FileSelectionPreviewResult(
            workspace_id=request.workspace_id,
            project_path=workspace.project_path,
            profile=request.file_rules_profile or "balanced",
            total_files=total_files,
            included_files_count=included_count,
            excluded_files_count=excluded_count,
            skipped_files_count=base_skipped_files,
            include_rules_count=len(include_rules),
            exclude_rules_count=len(exclude_rules),
            included_samples=included_samples,
            excluded_samples=excluded_samples,
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


@dataclass(frozen=True)
class _FileDecision:
    decision: str
    reason: str
    matched_rule: str | None = None


def _classify_file(
    path: str,
    include_rules: tuple[str, ...],
    exclude_rules: tuple[str, ...],
    gitignore_matcher: GitignoreMatcher | None = None,
) -> _FileDecision:
    exclude_rule = _first_matching_rule(path, exclude_rules)
    if exclude_rule is not None:
        return _FileDecision(
            decision="excluded",
            reason="Matched exclude rule",
            matched_rule=exclude_rule,
        )

    if gitignore_matcher is not None and gitignore_matcher.is_ignored(path):
        return _FileDecision(
            decision="excluded",
            reason="Ignored by .gitignore",
            matched_rule=".gitignore",
        )

    if include_rules:
        include_rule = _first_matching_rule(path, include_rules)
        if include_rule is None:
            return _FileDecision(
                decision="excluded",
                reason="Did not match include rules",
            )
        return _FileDecision(
            decision="included",
            reason="Matched include rule",
            matched_rule=include_rule,
        )

    return _FileDecision(decision="included", reason="Included by default")


def _first_matching_rule(path: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        if _matches_path(path, pattern):
            return pattern
    return None


def _normalize_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(pattern.strip() for pattern in patterns if pattern.strip())


def _matches_path(path: str, pattern: str) -> bool:
    normalized_path = path.lstrip("/")
    normalized_pattern = pattern.lstrip("/")
    if fnmatch(normalized_path, normalized_pattern):
        return True
    if normalized_pattern.endswith("/**"):
        prefix = normalized_pattern[:-3].rstrip("/")
        return normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
    return False
