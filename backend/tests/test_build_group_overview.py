"""Group overview aggregation: per-member facts + group rollups."""

from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.core.domain.git_insights import GitCommit, GitInsights
from app.core.domain.project_graph import (
    EntityType,
    ProjectEntity,
    ProjectFinding,
    ProjectGraph,
)
from app.core.domain.project_group import ProjectGroup
from app.core.use_cases.build_group_overview import BuildGroupOverviewUseCase


class _Workspace:
    def __init__(self, id, name, path):
        self.id = id
        self.name = name
        self.project_path = path
        self.assistant_mode = "developer"


class _WorkspaceRepo:
    def __init__(self, ws):
        self._w = {w.id: w for w in ws}

    def get(self, wid):
        return self._w.get(wid)


def _entity(t, name):
    return ProjectEntity(id=f"{t}:{name}", type=t, name=name, analyzer="test")


class _GraphRepo:
    def __init__(self, graphs):
        self._g = graphs

    def get_latest_graph(self, wid):
        return self._g.get(wid)


class _GitHistory:
    def __init__(self, by_path):
        self._by = by_path

    def read_insights(self, path):
        return self._by.get(path, GitInsights(is_repo=False))


def _graph(wid, services=0, envs=(), pipelines=(), infra=(), findings=()):
    ents = []
    ents += [_entity(EntityType.SERVICE, f"svc{i}") for i in range(services)]
    ents += [_entity(EntityType.ENVIRONMENT, e) for e in envs]
    ents += [_entity(EntityType.PIPELINE, p) for p in pipelines]
    ents += [_entity(EntityType.INFRA_COMPONENT, i) for i in infra]
    return ProjectGraph(workspace_id=wid, entities=ents, findings=list(findings))


def _finding(sev, title):
    return ProjectFinding(
        id=f"{sev}:{title}", category="c", severity=sev, title=title,
        explanation="e", analyzer="a",
    )


def _build():
    group_repo = InMemoryProjectGroupRepository()
    group_repo.add(ProjectGroup(id="g1", name="Platform", workspace_ids=("w1", "w2"), created_at="2026-06-01"))
    graphs = {
        "w1": _graph("w1", services=2, envs=("dev", "prod"), pipelines=("build",),
                     infra=("Terraform",), findings=(_finding("high", "No remote state"),)),
        "w2": _graph("w2", services=1, envs=("prod", "staging"), infra=("Helm",),
                     findings=(_finding("medium", "Public bucket"),)),
    }
    git = {
        "/p/w1": GitInsights(is_repo=True, branch="main", total_commits=100,
                             contributors_count=4, commits_last_7_days=10,
                             last_commit=GitCommit(short_hash="abc", subject="fix", author="a", committed_at="")),
        "/p/w2": GitInsights(is_repo=True, branch="main", total_commits=50,
                             contributors_count=2, commits_last_7_days=5),
    }
    uc = BuildGroupOverviewUseCase(
        group_repository=group_repo,
        workspace_repository=_WorkspaceRepo([
            _Workspace("w1", "api", "/p/w1"), _Workspace("w2", "web", "/p/w2"),
        ]),
        project_graph_repository=_GraphRepo(graphs),
        git_history=_GitHistory(git),
    )
    return uc


def test_overview_rolls_up_counts_and_unions_envs():
    ov = _build().execute("g1")
    assert ov.member_count == 2
    assert ov.totals["services"] == 3  # 2 + 1
    assert ov.totals["pipelines"] == 1
    assert ov.totals["commits_last_7_days"] == 15
    # environments unioned by name: dev, prod, staging
    assert ov.environments == ["dev", "prod", "staging"]
    assert "Terraform" in ov.technologies and "Helm" in ov.technologies


def test_overview_collects_repo_tagged_risks_high_first():
    ov = _build().execute("g1")
    assert ov.totals["risks_high"] == 1 and ov.totals["risks_medium"] == 1
    assert ov.risks[0].severity == "high" and ov.risks[0].workspace_name == "api"
    assert any(r.workspace_name == "web" and r.severity == "medium" for r in ov.risks)


def test_overview_member_git_and_description():
    ov = _build().execute("g1")
    api = next(m for m in ov.members if m.name == "api")
    assert api.built and api.is_repo and api.total_commits == 100
    assert api.last_commit_subject == "fix"
    assert "service(s)" in api.description and "dev" in api.description
