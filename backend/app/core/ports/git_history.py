from typing import Protocol

from app.core.domain.git_insights import GitInsights


class GitHistoryPort(Protocol):
    def read_insights(self, project_path: str) -> GitInsights:
        """Return a read-only snapshot of the project's git history.

        Implementations must never modify the repository and must degrade
        gracefully (returning ``GitInsights.not_a_repo()``) when the path is not
        a git repository or git is unavailable.
        """
