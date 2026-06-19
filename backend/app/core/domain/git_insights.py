from dataclasses import dataclass, field
from datetime import datetime, timedelta


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
    share: float = 0.0  # fraction of all-time commits (0..1)
    commits_last_90_days: int = 0
    last_active: str | None = None  # ISO date of most recent commit, if known


@dataclass(frozen=True)
class GitActivityBucket:
    period_start: str  # ISO date of the week's Monday
    commits: int


@dataclass(frozen=True)
class GitActivitySummary:
    weeks: list[GitActivityBucket]
    by_weekday: list[int]  # length 7, Monday..Sunday
    author_commits_90d: dict[str, int]
    author_last_active: dict[str, str]
    active_contributors: int


def summarize_activity(
    commits: list[tuple[datetime, str]], now: datetime, weeks_back: int = 12
) -> GitActivitySummary:
    """Pure aggregation of authored commits in the recent window.

    ``commits`` is a list of (committed_at, author). Returns weekly buckets
    (oldest→newest, always ``weeks_back`` long), a Monday..Sunday weekday
    histogram, and per-author recency/volume — everything the UI needs to show
    live activity without any further git calls.
    """
    this_monday = (now - timedelta(days=now.weekday())).date()
    week_starts = [this_monday - timedelta(weeks=(weeks_back - 1 - i)) for i in range(weeks_back)]
    week_index = {start: i for i, start in enumerate(week_starts)}
    week_counts = [0] * weeks_back
    weekday = [0] * 7
    author_90d: dict[str, int] = {}
    author_last: dict[str, str] = {}

    for committed_at, author in commits:
        d = committed_at.date()
        monday = d - timedelta(days=committed_at.weekday())
        idx = week_index.get(monday)
        if idx is not None:
            week_counts[idx] += 1
        weekday[committed_at.weekday()] += 1
        author_90d[author] = author_90d.get(author, 0) + 1
        iso = d.isoformat()
        if author not in author_last or iso > author_last[author]:
            author_last[author] = iso

    weeks = [
        GitActivityBucket(period_start=start.isoformat(), commits=count)
        for start, count in zip(week_starts, week_counts)
    ]
    return GitActivitySummary(
        weeks=weeks,
        by_weekday=weekday,
        author_commits_90d=author_90d,
        author_last_active=author_last,
        active_contributors=len(author_90d),
    )


@dataclass(frozen=True)
class GitFileHotspot:
    path: str
    changes: int


@dataclass(frozen=True)
class GitBranchStrategy:
    """A deterministic, honest reading of the repository's branching model.

    Inferred purely from branch *names* — never asserted. ``inferred_strategy``
    is one of "GitFlow", "GitHub Flow", "Trunk-based" or "Unknown", and
    ``rationale`` explains, in plain language, the evidence behind the guess.
    """

    default_branch: str | None
    total_branches: int
    long_lived_branches: list[str] = field(default_factory=list)
    prefixes: list[str] = field(default_factory=list)
    inferred_strategy: str = "Unknown"
    rationale: str = ""


# Branch-name prefixes that signal a workflow, and the canonical long-lived
# branch names. Used by the pure inference below so it stays testable.
_LONG_LIVED = {"main", "master", "develop", "development", "trunk"}
_KNOWN_PREFIXES = {
    "feature",
    "feat",
    "bugfix",
    "fix",
    "hotfix",
    "release",
    "support",
    "chore",
    "experiment",
}


def infer_branch_strategy(
    branches: list[str], default_branch: str | None
) -> GitBranchStrategy:
    """Infer a branching model from branch names. Pure and deterministic."""
    names = sorted({b.strip() for b in branches if b.strip()})
    lower = {n.lower() for n in names}
    long_lived = sorted(n for n in names if n.lower() in _LONG_LIVED)

    prefixes: set[str] = set()
    for name in names:
        if "/" in name:
            head = name.split("/", 1)[0].lower()
            if head in _KNOWN_PREFIXES:
                prefixes.add(head)
    prefixes_sorted = sorted(prefixes)

    has_main = bool(lower & {"main", "master"})
    has_develop = bool(lower & {"develop", "development"})
    has_release_or_hotfix = bool(prefixes & {"release", "hotfix"})
    has_feature = bool(prefixes & {"feature", "feat"})

    if has_develop and has_release_or_hotfix:
        strategy = "GitFlow"
        rationale = (
            "A long-lived develop branch alongside release/ or hotfix/ branches "
            "matches the GitFlow model."
        )
    elif has_main and has_feature and not has_develop:
        strategy = "GitHub Flow"
        rationale = (
            "Short-lived feature/ branches merging into a single main branch, with "
            "no develop branch, matches GitHub Flow."
        )
    elif has_main and len(names) <= 2 and not prefixes:
        strategy = "Trunk-based"
        rationale = (
            "Almost all work lands on a single main branch with few or no other "
            "branches, which looks trunk-based."
        )
    else:
        strategy = "Unknown"
        rationale = (
            "The branch names don't clearly match a common workflow; confirm the "
            "intended strategy with the team."
        )

    return GitBranchStrategy(
        default_branch=default_branch,
        total_branches=len(names),
        long_lived_branches=long_lived,
        prefixes=prefixes_sorted,
        inferred_strategy=strategy,
        rationale=rationale,
    )


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
    branch_strategy: GitBranchStrategy | None = None
    commits_last_7_days: int = 0
    commits_last_90_days: int = 0
    active_contributors_90d: int = 0
    merge_commit_share: float = 0.0  # fraction of merge commits over last 90 days
    recent_commits: list[GitCommit] = field(default_factory=list)
    activity_weeks: list[GitActivityBucket] = field(default_factory=list)
    activity_by_weekday: list[int] = field(default_factory=list)  # length 7, Mon..Sun

    @staticmethod
    def not_a_repo() -> "GitInsights":
        return GitInsights(is_repo=False)
