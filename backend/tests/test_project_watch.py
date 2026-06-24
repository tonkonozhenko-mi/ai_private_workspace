"""Project Watcher: graph diff, digest, and the run use case."""

from app.adapters.memory.in_memory_project_graph_repository import (
    InMemoryProjectGraphRepository,
)
from app.adapters.memory.in_memory_project_watch_repository import (
    InMemoryProjectWatchRepository,
)
from app.core.domain.project_graph import (
    EntityType,
    ProjectEntity,
    ProjectFinding,
    ProjectGraph,
)
from app.core.domain.project_watch import build_watch_digest, diff_graphs
from app.core.use_cases.run_project_watch import (
    RunProjectWatchInput,
    RunProjectWatchUseCase,
)


def _entity(eid, etype, name):
    return ProjectEntity(id=eid, type=etype, name=name, analyzer="x")


def _finding(fid, title, severity="medium"):
    return ProjectFinding(
        id=fid,
        category="reliability",
        severity=severity,
        title=title,
        explanation="...",
        analyzer="x",
    )


def _graph(entities, findings, analyzers=("terraform",)):
    return ProjectGraph(
        workspace_id="w1",
        entities=entities,
        findings=findings,
        analyzers_run=list(analyzers),
    )


def test_diff_baseline_when_no_previous():
    cur = _graph([_entity("environment:dev", EntityType.ENVIRONMENT, "dev")], [])
    diff = diff_graphs(None, cur)
    assert diff.is_baseline is True
    assert diff.has_changes is False


def test_diff_detects_added_removed_and_findings():
    prev = _graph(
        [_entity("service:api", EntityType.SERVICE, "api")],
        [_finding("f1", "Old risk")],
    )
    cur = _graph(
        [
            _entity("service:api", EntityType.SERVICE, "api"),
            _entity("environment:prod", EntityType.ENVIRONMENT, "prod"),
            _entity("cloud_service:aws-lambda", EntityType.CLOUD_SERVICE, "AWS · Lambda"),
        ],
        [_finding("f2", "New risk", "high")],
        analyzers=("terraform", "kubernetes"),
    )
    diff = diff_graphs(prev, cur)
    assert diff.has_changes is True
    added_names = {e.name for e in diff.added_entities}
    assert {"prod", "AWS · Lambda"} <= added_names
    assert [f.title for f in diff.added_findings] == ["New risk"]
    assert [f.title for f in diff.resolved_findings] == ["Old risk"]
    assert "kubernetes" in diff.added_analyzers


def test_digest_highlights_order_and_summary():
    prev = _graph([], [_finding("f1", "Old risk")])
    cur = _graph(
        [_entity("environment:prod", EntityType.ENVIRONMENT, "prod")],
        [_finding("f2", "New high risk", "high")],
        analyzers=("terraform", "helm"),
    )
    diff = diff_graphs(prev, cur)

    class _Meta:
        created_at = "2026-06-19T10:00:00+00:00"
        entity_count = 1
        finding_count = 1

    digest = build_watch_digest(diff, _Meta(), _Meta())
    assert digest["has_changes"] is True
    kinds = [h["kind"] for h in digest["highlights"]]
    # analyzer_added comes first, then risk_added, then entity_added.
    assert kinds[0] == "analyzer_added"
    assert "risk_added" in kinds and "entity_added" in kinds and "risk_resolved" in kinds
    assert "new risk" in digest["summary"].lower()


def test_no_change_digest():
    g = _graph([_entity("service:api", EntityType.SERVICE, "api")], [])

    class _Meta:
        created_at = "2026-06-19T10:00:00+00:00"
        entity_count = 1
        finding_count = 0

    digest = build_watch_digest(diff_graphs(g, g), _Meta(), _Meta())
    assert digest["has_changes"] is False
    assert "no changes" in digest["summary"].lower()


def test_run_use_case_persists_and_returns_digest():
    graph_repo = InMemoryProjectGraphRepository()
    watch_repo = InMemoryProjectWatchRepository()

    # Seed a previous snapshot.
    graph_repo.save_graph(_graph([_entity("service:api", EntityType.SERVICE, "api")], []))

    def build_graph(workspace_id):
        new_graph = _graph(
            [
                _entity("service:api", EntityType.SERVICE, "api"),
                _entity("environment:prod", EntityType.ENVIRONMENT, "prod"),
            ],
            [_finding("f1", "New risk", "high")],
        )
        return graph_repo.save_graph(new_graph)

    use_case = RunProjectWatchUseCase(graph_repo, watch_repo, build_graph)
    digest = use_case.execute(RunProjectWatchInput(workspace_id="w1"))

    assert digest["has_changes"] is True
    assert any(h["text"] == "New environment: prod" for h in digest["highlights"])
    # Persisted.
    assert watch_repo.get_latest_digest("w1") == digest


def test_run_use_case_baseline_on_first_run():
    graph_repo = InMemoryProjectGraphRepository()
    watch_repo = InMemoryProjectWatchRepository()

    def build_graph(workspace_id):
        return graph_repo.save_graph(
            _graph([_entity("service:api", EntityType.SERVICE, "api")], [])
        )

    digest = RunProjectWatchUseCase(graph_repo, watch_repo, build_graph).execute(
        RunProjectWatchInput(workspace_id="w1")
    )
    assert digest["baseline"] is True
