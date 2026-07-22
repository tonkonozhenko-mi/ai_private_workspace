"""Aggregate a group's members into one overview (Home + Intelligence).

For each member we read its persisted project graph (deterministic facts) and its
git history, then roll the numbers up to the group level. Everything is
best-effort per member: a repo that has never been analyzed simply shows
``built=False`` rather than breaking the group view.
"""

from __future__ import annotations

from app.core.domain.group_overview import (
    GroupMemberOverview,
    GroupMemberRisk,
    GroupOverview,
)
from app.core.domain.indexing_blind_spots import unread_files_in_scan
from app.core.domain.project_graph import EntityType, ProjectGraph
from app.core.domain.project_makeup import (
    MAKEUP_KEYS,
    describe_project,
    makeup_counts,
    technologies_of,
)
from app.core.domain.risk_explanation import explain_finding
from app.core.ports.git_history import GitHistoryPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_group_repository import ProjectGroupRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

# What the group counts. It used to count only the things a code repository is made
# of, so a wiki with a fully built map contributed nothing to any total and was
# announced as "Not analyzed yet" — the map was right there, and the aggregate was
# reading it for services and pipelines. The vocabulary is now the same one the single
# project uses, which is the only way the two views can ever agree.
_COUNT_KEYS = MAKEUP_KEYS


class BuildGroupOverviewNotFoundError(ValueError):
    pass


class BuildGroupOverviewUseCase:
    def __init__(
        self,
        group_repository: ProjectGroupRepositoryPort,
        workspace_repository: WorkspaceRepositoryPort,
        project_graph_repository: ProjectGraphRepositoryPort,
        git_history: GitHistoryPort,
        index_status_repository: IndexStatusRepositoryPort | None = None,
        project_scan_repository=None,
    ) -> None:
        self.group_repository = group_repository
        self.workspace_repository = workspace_repository
        self.project_graph_repository = project_graph_repository
        self.git_history = git_history
        self.index_status_repository = index_status_repository
        # Optional: read-only, used only to name the extensions a member could not
        # read. None leaves the member card exactly as it was.
        self.project_scan_repository = project_scan_repository

    def execute(self, group_id: str) -> GroupOverview:
        group = self.group_repository.get(group_id)
        if group is None:
            raise BuildGroupOverviewNotFoundError("Group not found")

        members: list[GroupMemberOverview] = []
        risks: list[GroupMemberRisk] = []
        for workspace_id in group.workspace_ids:
            workspace = self.workspace_repository.get(workspace_id)
            if workspace is None:
                continue
            member, member_risks = self._member(workspace_id, workspace)
            members.append(member)
            risks.extend(member_risks)

        return GroupOverview(
            group_id=group.id,
            name=group.name,
            member_count=len(members),
            totals=self._totals(members, risks),
            environments=self._union(m.environments for m in members),
            technologies=self._union(m.technology_chips for m in members),
            risks=sorted(risks, key=lambda r: (_severity_rank(r.severity), r.workspace_name)),
            members=members,
        )

    def _member(self, workspace_id, workspace):
        graph = self.project_graph_repository.get_latest_graph(workspace_id)
        built = graph is not None
        counts = makeup_counts(graph)
        environments = (
            [e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT)] if graph else []
        )
        chips = technologies_of(graph)
        risk_counts, member_risks = self._risks(graph, workspace_id, workspace.name)
        git = self._git(workspace.project_path)
        member = GroupMemberOverview(
            workspace_id=workspace_id,
            name=workspace.name,
            project_path=workspace.project_path,
            built=built,
            indexed=self._indexed(workspace_id),
            description=describe_project(graph),
            technology_chips=chips,
            counts=counts,
            environments=environments,
            risk_counts=risk_counts,
            unreadable_by_extension=self._unreadable(workspace_id),
            **git,
        )
        return member, member_risks

    def _unreadable(self, workspace_id: str) -> dict[str, int]:
        if self.project_scan_repository is None:
            return {}
        try:
            scan = self.project_scan_repository.get_latest_scan(workspace_id)
        except Exception:
            # A member whose scan cannot be read is a member with nothing to say
            # about its blind spots — not a member with none.
            return {}
        return unread_files_in_scan(scan).summary()

    @staticmethod
    def _risks(graph: ProjectGraph | None, workspace_id: str, workspace_name: str):
        counts: dict[str, int] = {}
        items: list[GroupMemberRisk] = []
        if graph is None:
            return counts, items
        for finding in graph.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
            if finding.severity in ("high", "medium"):
                items.append(
                    GroupMemberRisk(
                        workspace_id=workspace_id,
                        workspace_name=workspace_name,
                        severity=finding.severity,
                        # The same word the single project uses. A risk does not become
                        # a different kind of thing by being seen from a group.
                        attention=explain_finding(finding).attention,
                        title=finding.title,
                        explanation=finding.explanation,
                        recommendation=finding.recommendation,
                        category=finding.category,
                        source_file=finding.source_file,
                    )
                )
        return counts, items

    def _git(self, project_path: str) -> dict:
        try:
            insights = self.git_history.read_insights(project_path)
        except Exception:  # noqa: BLE001 - git is best-effort, never fatal
            # The call blew up, so we know nothing — which is not the same as
            # knowing this is not a repository.
            return {
                "git_known": False,
                "is_repo": False,
                "branch": None,
                "total_commits": 0,
                "contributors_count": 0,
                "commits_last_7_days": 0,
                "last_commit_subject": None,
            }
        # Prefer the project's main line (default branch) over whatever feature
        # branch happens to be checked out — matches the single-project view.
        default_branch = (
            insights.branch_strategy.default_branch if insights.branch_strategy else None
        )
        return {
            "git_known": insights.known,
            "is_repo": insights.is_repo,
            "branch": default_branch or insights.branch,
            "total_commits": insights.total_commits,
            "contributors_count": insights.contributors_count,
            "commits_last_7_days": insights.commits_last_7_days,
            "last_commit_subject": insights.last_commit.subject if insights.last_commit else None,
        }

    def _indexed(self, workspace_id: str) -> bool:
        if self.index_status_repository is None:
            return False
        status = self.index_status_repository.get(workspace_id)
        return status is not None and status.status != "not_indexed"

    @staticmethod
    def _totals(members: list[GroupMemberOverview], risks: list[GroupMemberRisk]) -> dict[str, int]:
        totals = {k: 0 for k in _COUNT_KEYS}
        commits_7d = 0
        for member in members:
            for key in _COUNT_KEYS:
                totals[key] += member.counts.get(key, 0)
            commits_7d += member.commits_last_7_days
        totals["repos"] = len(members)
        totals["commits_last_7_days"] = commits_7d
        totals["risks_high"] = sum(1 for r in risks if r.severity == "high")
        totals["risks_medium"] = sum(1 for r in risks if r.severity == "medium")
        return totals

    @staticmethod
    def _union(name_lists) -> list[str]:
        seen: list[str] = []
        for names in name_lists:
            for name in names:
                if name not in seen:
                    seen.append(name)
        return sorted(seen)


def _severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2, "info": 3}.get(severity, 4)
