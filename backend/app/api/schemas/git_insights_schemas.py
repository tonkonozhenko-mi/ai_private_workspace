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


class GitFileHotspotResponse(BaseModel):
    path: str
    changes: int


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
            GitContributorResponse(name=c.name, commits=c.commits)
            for c in insights.top_contributors
        ],
        hotspots=[
            GitFileHotspotResponse(path=h.path, changes=h.changes) for h in insights.hotspots
        ],
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
