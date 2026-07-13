"""Aggregated view of a group: each member's headline facts plus group rollups.

This is the data behind a group's Home and Intelligence — the program treating
the whole group as one project. Every per-repo number stays attributed to its
repository so the combined view is auditable.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GroupMemberRisk:
    workspace_id: str
    workspace_name: str
    severity: str
    # The same softened word the single project uses ("Worth a close look"), because a
    # risk does not become a different kind of thing by being seen from a group. Two
    # vocabularies for one fact — "HIGH" here, "worth a close look" there — is how a
    # person learns not to trust either.
    attention: str = ""
    title: str = ""
    # Same human-readable detail a single-repo risk card carries, so a group risk
    # can be understood and acted on without opening the member project.
    explanation: str = ""
    recommendation: str | None = None
    category: str = ""
    source_file: str | None = None


@dataclass(frozen=True)
class GroupMemberOverview:
    workspace_id: str
    name: str
    project_path: str
    built: bool
    indexed: bool
    description: str
    technology_chips: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    environments: list[str] = field(default_factory=list)
    risk_counts: dict[str, int] = field(default_factory=dict)
    # git
    is_repo: bool = False
    branch: str | None = None
    total_commits: int = 0
    contributors_count: int = 0
    commits_last_7_days: int = 0
    last_commit_subject: str | None = None


@dataclass(frozen=True)
class GroupOverview:
    group_id: str
    name: str
    member_count: int
    totals: dict[str, int] = field(default_factory=dict)
    environments: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    risks: list[GroupMemberRisk] = field(default_factory=list)
    members: list[GroupMemberOverview] = field(default_factory=list)
