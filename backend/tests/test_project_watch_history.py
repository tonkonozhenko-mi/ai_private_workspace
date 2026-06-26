"""Change-history: domain entry builder, repository, and use-case auto-logging."""

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
from app.core.domain.project_watch import build_watch_history_entry
from app.core.use_cases.run_project_watch import (
    RunProjectWatchInput,
    RunProjectWatchUseCase,
)


# -- domain entry builder ---------------------------------------------------


def test_history_entry_skips_baseline_and_unchanged():
    assert build_watch_history_entry({"baseline": True, "has_changes": False}) is None
    assert build_watch_history_entry({"has_changes": False}) is None
    assert build_watch_history_entry({}) is None


def test_history_entry_captures_changed_digest():
    digest = {
        "has_changes": True,
        "checked_at": "2026-06-26T10:00:00+00:00",
        "summary": "Since the last check: 1 new risk(s).",
        "git_head": "abc123",
        "counts": {"findings_added": 1},
        "highlights": [{"text": "New risk", "kind": "risk_added"}],
        "git_brief": {
            "commit_count": 3,
            "commit_subjects": ["fix a", "add b", "tune c"],
            "authors": ["Alice"],
        },
    }
    entry = build_watch_history_entry(digest)
    assert entry is not None
    assert entry["checked_at"] == "2026-06-26T10:00:00+00:00"
    assert entry["llm_summary"] is None
    assert entry["commit_count"] == 3
    assert entry["commit_subjects"] == ["fix a", "add b", "tune c"]
    assert entry["git_head"] == "abc123"


# -- repository -------------------------------------------------------------


def test_repository_history_append_list_and_summary():
    repo = InMemoryProjectWatchRepository()
    repo.append_history("w1", {"summary": "first", "llm_summary": None})
    repo.append_history("w1", {"summary": "second", "llm_summary": None})

    entries = repo.list_history("w1")
    assert [e["summary"] for e in entries] == ["second", "first"]  # newest first
    assert all("id" in e and "created_at" in e for e in entries)

    repo.set_latest_history_summary("w1", "human summary")
    assert repo.list_history("w1")[0]["llm_summary"] == "human summary"

    repo.clear("w1")
    assert repo.list_history("w1") == []


def test_repository_history_isolated_per_workspace():
    repo = InMemoryProjectWatchRepository()
    repo.append_history("w1", {"summary": "a"})
    assert repo.list_history("w2") == []


# -- use case auto-logs a changed check -------------------------------------


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


def test_run_use_case_appends_history_on_change():
    graph_repo = InMemoryProjectGraphRepository()
    watch_repo = InMemoryProjectWatchRepository()
    graph_repo.save_graph(_graph([_entity("service:api", EntityType.SERVICE, "api")], []))

    def build_graph(workspace_id):
        return graph_repo.save_graph(
            _graph(
                [
                    _entity("service:api", EntityType.SERVICE, "api"),
                    _entity("environment:prod", EntityType.ENVIRONMENT, "prod"),
                ],
                [_finding("f1", "New risk", "high")],
            )
        )

    RunProjectWatchUseCase(graph_repo, watch_repo, build_graph).execute(
        RunProjectWatchInput(workspace_id="w1")
    )
    history = watch_repo.list_history("w1")
    assert len(history) == 1
    assert history[0]["counts"]["findings_added"] == 1


def test_run_use_case_does_not_log_baseline():
    graph_repo = InMemoryProjectGraphRepository()
    watch_repo = InMemoryProjectWatchRepository()

    def build_graph(workspace_id):
        return graph_repo.save_graph(
            _graph([_entity("service:api", EntityType.SERVICE, "api")], [])
        )

    RunProjectWatchUseCase(graph_repo, watch_repo, build_graph).execute(
        RunProjectWatchInput(workspace_id="w1")
    )
    assert watch_repo.list_history("w1") == []
