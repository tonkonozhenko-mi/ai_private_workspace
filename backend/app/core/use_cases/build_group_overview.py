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
from app.core.domain.project_graph import EntityType, ProjectGraph
from app.core.ports.git_history import GitHistoryPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_group_repository import ProjectGroupRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

_COUNT_KEYS = ("services", "environments", "pipelines", "infrastructure")


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
    ) -> None:
        self.group_repository = group_repository
        self.workspace_repository = workspace_repository
        self.project_graph_repository = project_graph_repository
        self.git_history = git_history
        self.index_status_repository = index_status_repository

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
        counts = self._counts(graph)
        environments = (
            [e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT)] if graph else []
        )
        chips = self._chips(graph)
        risk_counts, member_risks = self._risks(graph, workspace_id, workspace.name)
        git = self._git(workspace.project_path)
        member = GroupMemberOverview(
            workspace_id=workspace_id,
            name=workspace.name,
            project_path=workspace.project_path,
            built=built,
            indexed=self._indexed(workspace_id),
            description=self._describe(workspace.name, counts, environments),
            technology_chips=chips,
            counts=counts,
            environments=environments,
            risk_counts=risk_counts,
            **git,
        )
        return member, member_risks

    @staticmethod
    def _counts(graph: ProjectGraph | None) -> dict[str, int]:
        if graph is None:
            return {k: 0 for k in _COUNT_KEYS}
        return {
            "services": len(graph.entities_of_type(EntityType.SERVICE)),
            "environments": len(graph.entities_of_type(EntityType.ENVIRONMENT)),
            "pipelines": len(graph.entities_of_type(EntityType.PIPELINE)),
            "infrastructure": len(graph.entities_of_type(EntityType.INFRA_COMPONENT)),
        }

    @staticmethod
    def _chips(graph: ProjectGraph | None) -> list[str]:
        if graph is None:
            return []
        names: set[str] = set()
        for entity_type in (
            EntityType.INFRA_COMPONENT,
            EntityType.PIPELINE,
            EntityType.DEPENDENCY,
        ):
            names |= {e.name for e in graph.entities_of_type(entity_type)}
        return sorted(names)

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
                        title=finding.title,
                    )
                )
        return counts, items

    def _git(self, project_path: str) -> dict:
        try:
            insights = self.git_history.read_insights(project_path)
        except Exception:  # noqa: BLE001 - git is best-effort, never fatal
            return {
                "is_repo": False,
                "branch": None,
                "total_commits": 0,
                "contributors_count": 0,
                "commits_last_7_days": 0,
                "last_commit_subject": None,
            }
        return {
            "is_repo": insights.is_repo,
            "branch": insights.branch,
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
    def _describe(name: str, counts: dict[str, int], environments: list[str]) -> str:
        parts: list[str] = []
        if counts.get("services"):
            parts.append(f"{counts['services']} service(s)")
        if environments:
            parts.append(f"{len(environments)} env(s): " + ", ".join(environments))
        if counts.get("pipelines"):
            parts.append(f"{counts['pipelines']} pipeline(s)")
        return "; ".join(parts) if parts else "Not analyzed yet."

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
