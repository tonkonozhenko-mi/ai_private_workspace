from collections.abc import Callable
from dataclasses import dataclass

from app.core.domain.indexing_rules import (
    DEFAULT_INCLUDE_PATTERNS,
    default_indexing_rules,
)
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.skill_registry import SkillRegistry
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)
from app.core.use_cases.scan_project import ScanProjectInput, ScanProjectUseCase


@dataclass(frozen=True)
class ScanWorkspaceProjectInput:
    workspace_id: str
    # None = "use this workspace's own file rules". () = "explicitly none".
    # They used to be the same value, so a caller that simply did not mention
    # rules silently scanned by different ones than everybody else reads by.
    include_patterns: tuple[str, ...] | None = None
    exclude_patterns: tuple[str, ...] | None = None
    file_rules_profile: str | None = None
    cancellation_check: Callable[[], bool] | None = None
    progress_callback: Callable[[int, int, str], None] | None = None


class WorkspaceNotFoundError(ValueError):
    pass


class ScanWorkspaceProjectUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        file_system: FileSystemPort,
        project_scan_repository: ProjectScanRepositoryPort,
        skill_registry: SkillRegistry | None = None,
        timeline_repository: TimelineRepositoryPort | None = None,
        indexing_rules_repository=None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.file_system = file_system
        self.project_scan_repository = project_scan_repository
        self.skill_registry = skill_registry
        self.timeline_repository = timeline_repository
        # Which files this workspace is made of is a property of the workspace,
        # so the scan asks it rather than waiting to be told. Optional: without
        # it the input's own patterns are used exactly as before.
        self.indexing_rules_repository = indexing_rules_repository

    def _rules(self, request: ScanWorkspaceProjectInput) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return resolve_scan_rules(
            self.indexing_rules_repository,
            request.workspace_id,
            request.include_patterns,
            request.exclude_patterns,
        )

    def execute(self, request: ScanWorkspaceProjectInput) -> ProjectScanResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("Workspace not found")

        include_patterns, exclude_patterns = self._rules(request)

        scan_result = ScanProjectUseCase(
            file_system=self.file_system,
            skill_registry=self.skill_registry,
        ).execute(
            ScanProjectInput(
                project_path=workspace.project_path,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                # Whether these rules are ours or the person's decides what a
                # cut file means: something we failed to see, or something they
                # did not ask for. Comparing the tuples is enough — rules that
                # happen to equal the defaults *are* the defaults.
                include_patterns_are_default=include_patterns == DEFAULT_INCLUDE_PATTERNS,
                cancellation_check=request.cancellation_check,
                progress_callback=request.progress_callback,
            )
        )

        self.project_scan_repository.save_latest_scan(
            workspace_id=request.workspace_id,
            scan_result=scan_result,
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="project_scanned",
                    title="Project scanned",
                    summary=(
                        f"Scanned {scan_result.scanned_files} files and detected "
                        f"{len(scan_result.detected_skills)} skills."
                    ),
                    metadata={
                        "total_files": str(scan_result.total_files),
                        "detected_skills_count": str(len(scan_result.detected_skills)),
                        "include_rules_count": str(len(request.include_patterns)),
                        "exclude_rules_count": str(len(request.exclude_patterns)),
                        "include_patterns": _join_patterns(request.include_patterns) or "All files",
                        "exclude_patterns": _join_patterns(request.exclude_patterns)
                        or "No exclusions",
                        "file_rules_profile": request.file_rules_profile or "none",
                    },
                )
            )
        return scan_result


def _join_patterns(patterns: tuple[str, ...]) -> str:
    return " · ".join(pattern for pattern in patterns if pattern.strip())


def resolve_scan_rules(
    indexing_rules_repository,
    workspace_id: str,
    include_patterns: tuple[str, ...] | None,
    exclude_patterns: tuple[str, ...] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Which files this workspace is made of.

    Everything that reads a scan must agree with whatever wrote it, or the two
    are describing different projects. The watcher's rebuild passed no rules at
    all and persisted the result as the baseline, while the change check read it
    back through the workspace's own rules — so a file the walk takes and the
    rules do not was "removed" on every check, for ever, and no rescan could
    clear it because every rescan wrote the same mismatch again.

    None means "this workspace's rules"; an explicit tuple overrides them (the
    scan screen lets you preview a different selection). Callers that simply do
    not mention rules now get the right ones instead of none.
    """
    if include_patterns is not None and exclude_patterns is not None:
        return include_patterns, exclude_patterns
    profile = None
    if indexing_rules_repository is not None:
        profile = indexing_rules_repository.get(workspace_id)
    if profile is None:
        profile = default_indexing_rules(workspace_id)
    return (
        include_patterns if include_patterns is not None else profile.include_patterns,
        exclude_patterns if exclude_patterns is not None else profile.exclude_patterns,
    )
