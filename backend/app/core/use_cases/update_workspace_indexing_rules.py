from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.domain.indexing_rules import IndexingRulesProfile, normalize_patterns
from app.core.ports.indexing_rules_repository import IndexingRulesRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import AddTimelineEventInput, AddTimelineEventUseCase


@dataclass(frozen=True)
class UpdateWorkspaceIndexingRulesInput:
    workspace_id: str
    profile: str
    include_patterns: tuple[str, ...]
    exclude_patterns: tuple[str, ...]


class UpdateWorkspaceIndexingRulesNotFoundError(ValueError):
    pass


class UpdateWorkspaceIndexingRulesValidationError(ValueError):
    pass


class UpdateWorkspaceIndexingRulesUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        indexing_rules_repository: IndexingRulesRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.indexing_rules_repository = indexing_rules_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: UpdateWorkspaceIndexingRulesInput) -> IndexingRulesProfile:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise UpdateWorkspaceIndexingRulesNotFoundError("Workspace not found")
        profile = request.profile.strip() or "balanced"
        include_patterns = normalize_patterns(request.include_patterns)
        exclude_patterns = normalize_patterns(request.exclude_patterns)
        if len(include_patterns) > 80 or len(exclude_patterns) > 80:
            raise UpdateWorkspaceIndexingRulesValidationError("Too many indexing rules")
        saved = self.indexing_rules_repository.save(
            IndexingRulesProfile(
                workspace_id=request.workspace_id,
                profile=profile,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="indexing_rules_updated",
                    title="Indexing rules updated",
                    summary="Saved workspace file selection rules.",
                    metadata={
                        "profile": saved.profile,
                        "include_rules_count": str(saved.include_rules_count),
                        "exclude_rules_count": str(saved.exclude_rules_count),
                    },
                )
            )
        return saved
