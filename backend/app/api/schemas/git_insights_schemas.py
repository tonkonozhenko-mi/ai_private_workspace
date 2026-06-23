from pydantic import BaseModel

from app.core.domain.git_insights import GitInsights


class GitCommitResponse(BaseModel):
    short_hash: str
    subject: str
    author: str
    committed_at: str


class GitContributorResponse(BaseModel):
    name: str
    commits: int
    share: float = 0.0
    commits_last_90_days: int = 0
    last_active: str | None = None


class GitFileHotspotResponse(BaseModel):
    path: str
    changes: int


class GitFileCouplingResponse(BaseModel):
    file_a: str
    file_b: str
    together: int
    share: float = 0.0


class GitFileActivityResponse(BaseModel):
    path: str | None = None
    total_commits: int = 0
    top_authors: list[GitContributorResponse] = []
    recent_commits: list[GitCommitResponse] = []


class GitActivityBucketResponse(BaseModel):
    period_start: str
    commits: int


class GitMergeActivityResponse(BaseModel):
    merge_commits: int = 0
    pull_requests_detected: int = 0
    merge_requests_detected: int = 0
    source_branch_types: dict[str, int] = {}
    target_branches: dict[str, int] = {}


class GitBranchStrategyResponse(BaseModel):
    default_branch: str | None = None
    total_branches: int = 0
    long_lived_branches: list[str] = []
    prefixes: list[str] = []
    inferred_strategy: str = "Unknown"
    rationale: str = ""


class GitInsightsResponse(BaseModel):
    is_repo: bool
    branch: str | None = None
    last_commit: GitCommitResponse | None = None
    total_commits: int = 0
    commits_last_30_days: int = 0
    contributors_count: int = 0
    first_commit_at: str | None = None
    top_contributors: list[GitContributorResponse] = []
    hotspots: list[GitFileHotspotResponse] = []
    branch_strategy: GitBranchStrategyResponse | None = None
    commits_last_7_days: int = 0
    commits_last_90_days: int = 0
    active_contributors_90d: int = 0
    merge_commit_share: float = 0.0
    recent_commits: list[GitCommitResponse] = []
    activity_weeks: list[GitActivityBucketResponse] = []
    activity_by_weekday: list[int] = []
    merge_activity: GitMergeActivityResponse | None = None
    file_couplings: list[GitFileCouplingResponse] = []


def to_git_insights_response(insights: GitInsights) -> GitInsightsResponse:
    return GitInsightsResponse(
        is_repo=insights.is_repo,
        branch=insights.branch,
        last_commit=(
            GitCommitResponse(
                short_hash=insights.last_commit.short_hash,
                subject=insights.last_commit.subject,
                author=insights.last_commit.author,
                committed_at=insights.last_commit.committed_at,
            )
            if insights.last_commit is not None
            else None
        ),
        total_commits=insights.total_commits,
        commits_last_30_days=insights.commits_last_30_days,
        contributors_count=insights.contributors_count,
        first_commit_at=insights.first_commit_at,
        top_contributors=[
            GitContributorResponse(
                name=c.name,
                commits=c.commits,
                share=c.share,
                commits_last_90_days=c.commits_last_90_days,
                last_active=c.last_active,
            )
            for c in insights.top_contributors
        ],
        hotspots=[
            GitFileHotspotResponse(path=h.path, changes=h.changes) for h in insights.hotspots
        ],
        commits_last_7_days=insights.commits_last_7_days,
        commits_last_90_days=insights.commits_last_90_days,
        active_contributors_90d=insights.active_contributors_90d,
        merge_commit_share=insights.merge_commit_share,
        recent_commits=[
            GitCommitResponse(
                short_hash=c.short_hash,
                subject=c.subject,
                author=c.author,
                committed_at=c.committed_at,
            )
            for c in insights.recent_commits
        ],
        activity_weeks=[
            GitActivityBucketResponse(period_start=b.period_start, commits=b.commits)
            for b in insights.activity_weeks
        ],
        activity_by_weekday=list(insights.activity_by_weekday),
        file_couplings=[
            GitFileCouplingResponse(
                file_a=c.file_a, file_b=c.file_b, together=c.together, share=c.share
            )
            for c in insights.file_couplings
        ],
        merge_activity=(
            GitMergeActivityResponse(
                merge_commits=insights.merge_activity.merge_commits,
                pull_requests_detected=insights.merge_activity.pull_requests_detected,
                merge_requests_detected=insights.merge_activity.merge_requests_detected,
                source_branch_types=dict(insights.merge_activity.source_branch_types),
                target_branches=dict(insights.merge_activity.target_branches),
            )
            if insights.merge_activity is not None
            else None
        ),
        branch_strategy=(
            GitBranchStrategyResponse(
                default_branch=insights.branch_strategy.default_branch,
                total_branches=insights.branch_strategy.total_branches,
                long_lived_branches=list(insights.branch_strategy.long_lived_branches),
                prefixes=list(insights.branch_strategy.prefixes),
                inferred_strategy=insights.branch_strategy.inferred_strategy,
                rationale=insights.branch_strategy.rationale,
            )
            if insights.branch_strategy is not None
            else None
        ),
    )
