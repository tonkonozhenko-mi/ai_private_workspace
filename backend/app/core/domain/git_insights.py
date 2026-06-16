from dataclasses import dataclass, field


@dataclass(frozen=True)
class GitCommit:
    short_hash: str
    subject: str
    author: str
    committed_at: str  # ISO 8601, or "" if unknown


@dataclass(frozen=True)
class GitContributor:
    name: str
    commits: int


@dataclass(frozen=True)
class GitFileHotspot:
    path: str
    changes: int


@dataclass(frozen=True)
class GitInsights:
    """A small, read-only snapshot of a project's git history.

    Everything here comes from read-only ``git`` queries. When the project is
    not a git repository (or git is unavailable), ``is_repo`` is ``False`` and
    the remaining fields stay at their empty defaults.
    """

    is_repo: bool
    branch: str | None = None
    last_commit: GitCommit | None = None
    total_commits: int = 0
    commits_last_30_days: int = 0
    contributors_count: int = 0
    first_commit_at: str | None = None
    top_contributors: list[GitContributor] = field(default_factory=list)
    hotspots: list[GitFileHotspot] = field(default_factory=list)

    @staticmethod
    def not_a_repo() -> "GitInsights":
        return GitInsights(is_repo=False)
