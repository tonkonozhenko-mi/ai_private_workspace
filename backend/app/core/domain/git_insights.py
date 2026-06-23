import re
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
class GitFileCoupling:
    """Two files that tend to change in the same commits (temporal coupling).

    High coupling between files in *different* modules is a tell of a hidden
    dependency the static import graph misses — change one and you almost always
    have to change the other.
    """

    file_a: str
    file_b: str
    together: int  # commits where both files changed
    share: float  # together / min(changes_a, changes_b), 0..1


def compute_couplings(
    commit_files: list[list[str]],
    *,
    min_together: int = 3,
    max_files_per_commit: int = 30,
    limit: int = 8,
) -> list[GitFileCoupling]:
    """Find file pairs that change together, from a list of per-commit file lists.

    Pure and deterministic. Commits touching a huge number of files (sweeping
    renames, formatting, vendored drops) are skipped — they couple everything to
    everything and only add noise. ``share`` is the conditional rate: of the
    times the rarer of the two files changed, how often the other changed too.
    """
    from itertools import combinations

    pair_counts: dict[tuple[str, str], int] = {}
    file_counts: dict[str, int] = {}
    for files in commit_files:
        unique = sorted({f for f in files if f})
        if len(unique) < 2 or len(unique) > max_files_per_commit:
            continue
        for f in unique:
            file_counts[f] = file_counts.get(f, 0) + 1
        for a, b in combinations(unique, 2):
            pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    results: list[GitFileCoupling] = []
    for (a, b), together in pair_counts.items():
        if together < min_together:
            continue
        denom = min(file_counts.get(a, 0), file_counts.get(b, 0)) or 1
        results.append(
            GitFileCoupling(file_a=a, file_b=b, together=together, share=round(together / denom, 3))
        )
    results.sort(key=lambda c: (-c.share, -c.together, c.file_a, c.file_b))
    return results[:limit]


@dataclass(frozen=True)
class GitFileActivity:
    """Ownership + recent-change activity for a file (or the whole repo when
    ``path`` is None). Read-only, from git history."""

    path: str | None
    total_commits: int
    top_authors: list["GitContributor"]
    recent_commits: list["GitCommit"]


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
class GitMergeActivity:
    """Approximate pull/merge-request activity, inferred from merge-commit
    messages and ``(#N)`` / ``!N`` references. Honest by nature: squash- and
    rebase-merged PRs are only partially visible, so this is a lower bound."""

    merge_commits: int
    pull_requests_detected: int  # distinct #N (GitHub-style)
    merge_requests_detected: int  # distinct !N (GitLab-style)
    source_branch_types: dict[str, int] = field(default_factory=dict)
    target_branches: dict[str, int] = field(default_factory=dict)


_MERGE_PR_RE = re.compile(r"Merge pull request #(\d+) from [^/\s]+/(\S+)")
_MERGE_BRANCH_RE = re.compile(r"Merge branch '([^']+)'(?:\s+into '([^']+)')?")
_PR_REF_RE = re.compile(r"#(\d+)")
_MR_REF_RE = re.compile(r"!(\d+)")
_BRANCH_PREFIXES = {"feature", "feat", "bugfix", "fix", "hotfix", "release", "chore"}


def _branch_type(branch: str) -> str:
    head = branch.split("/", 1)[0].lower() if "/" in branch else ""
    return head if head in _BRANCH_PREFIXES else "other"


def summarize_merges(
    merge_subjects: list[str], all_subjects: list[str]
) -> GitMergeActivity:
    """Pure aggregation of merge/PR signals from commit subjects."""
    source_types: dict[str, int] = {}
    targets: dict[str, int] = {}

    for subject in merge_subjects:
        pr = _MERGE_PR_RE.search(subject)
        if pr:
            source = pr.group(2)
            source_types[_branch_type(source)] = source_types.get(_branch_type(source), 0) + 1
            continue
        mb = _MERGE_BRANCH_RE.search(subject)
        if mb:
            source = mb.group(1)
            target = mb.group(2)
            source_types[_branch_type(source)] = source_types.get(_branch_type(source), 0) + 1
            if target:
                targets[target] = targets.get(target, 0) + 1

    prs = {m for s in all_subjects for m in _PR_REF_RE.findall(s)}
    mrs = {m for s in all_subjects for m in _MR_REF_RE.findall(s)}

    return GitMergeActivity(
        merge_commits=len(merge_subjects),
        pull_requests_detected=len(prs),
        merge_requests_detected=len(mrs),
        source_branch_types=dict(sorted(source_types.items(), key=lambda kv: -kv[1])),
        target_branches=dict(sorted(targets.items(), key=lambda kv: -kv[1])),
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
    merge_activity: GitMergeActivity | None = None
    file_couplings: list[GitFileCoupling] = field(default_factory=list)

    @staticmethod
    def not_a_repo() -> "GitInsights":
        return GitInsights(is_repo=False)
