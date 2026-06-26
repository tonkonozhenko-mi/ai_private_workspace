"""Change-history: domain entry builder, repository, and use-case auto-logging."""

from types import SimpleNamespace

from app.adapters.memory.in_memory_project_graph_repository import (
    InMemoryProjectGraphRepository,
)
from app.adapters.memory.in_memory_project_watch_repository import (
    InMemoryProjectWatchRepository,
)
from app.core.domain.git_change_brief import GitChangeBrief, changed_files_by_area
from app.core.domain.project_graph import (
    EntityType,
    ProjectEntity,
    ProjectFinding,
    ProjectGraph,
)
from app.core.domain.project_watch import build_git_only_digest, build_watch_history_entry
from app.core.use_cases.record_git_history import (
    RecordGitHistoryInput,
    RecordGitHistoryUseCase,
)
from app.core.use_cases.run_project_watch import (
    RunProjectWatchInput,
    RunProjectWatchUseCase,
)

# -- domain entry builder ---------------------------------------------------


def test_changed_files_by_area_groups_with_paths():
    areas = changed_files_by_area(
        [
            "applications/a/main.tf",
            "applications/b/main.tf",
            "accounts/x/vars.tf",
            "README.md",
        ]
    )
    # Most-changed area first; each area carries its actual file paths.
    assert areas[0]["area"] == "applications"
    assert areas[0]["files"] == 2
    assert areas[0]["paths"] == ["applications/a/main.tf", "applications/b/main.tf"]
    root = next(a for a in areas if a["area"] == "(root)")
    assert root["paths"] == ["README.md"]


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
            "lines": ["3 commits by Alice", "Most changes in applications (2 files)"],
            "areas": [{"area": "applications", "files": 2}],
        },
    }
    entry = build_watch_history_entry(digest)
    assert entry is not None
    assert entry["checked_at"] == "2026-06-26T10:00:00+00:00"
    assert entry["llm_summary"] is None
    assert entry["commit_count"] == 3
    assert entry["commit_subjects"] == ["fix a", "add b", "tune c"]
    assert entry["git_head"] == "abc123"
    assert entry["areas"] == [{"area": "applications", "files": 2}]
    assert entry["git_lines"][1].startswith("Most changes")


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


# -- git-only (cheap) history recorder --------------------------------------


def test_git_only_digest_shape():
    brief = GitChangeBrief(
        comparable=True,
        head="def456",
        commit_count=2,
        authors=["Bob"],
        changed_paths=["applications/a.tf", "applications/b.tf"],
        commit_subjects=["x", "y"],
    )
    digest = build_git_only_digest(brief, "2026-06-26T12:00:00+00:00")
    assert digest["has_changes"] is True
    assert digest["git_head"] == "def456"
    assert digest["highlights"] == []  # structural needs a full check
    assert digest["git_brief"]["areas"][0]["area"] == "applications"


class _WSRepo2:
    def get(self, wid):
        return SimpleNamespace(id=wid, project_path="/p") if wid == "w1" else None


def test_record_git_history_uses_cursor_and_logs(monkeypatch):
    watch_repo = InMemoryProjectWatchRepository()
    seen = {}

    def provider(wid, since):
        seen["since"] = since
        return GitChangeBrief(
            comparable=True,
            head="h2",
            commit_count=3,
            authors=["Bob"],
            changed_paths=["accounts/x.tf"],
            commit_subjects=["a", "b", "c"],
        )

    uc = RecordGitHistoryUseCase(_WSRepo2(), watch_repo, provider)
    uc.execute(RecordGitHistoryInput(workspace_id="w1"))

    # First record: cursor was empty, then advanced to the new HEAD.
    assert seen["since"] is None
    assert watch_repo.get_history_cursor("w1") == "h2"
    history = watch_repo.list_history("w1")
    assert len(history) == 1 and history[0]["commit_count"] == 3

    # Second record reads from the advanced cursor.
    uc.execute(RecordGitHistoryInput(workspace_id="w1"))
    assert seen["since"] == "h2"


def test_record_git_history_baseline_advances_cursor_without_entry():
    watch_repo = InMemoryProjectWatchRepository()

    def provider(wid, since):
        # No baseline yet → not comparable, no commits, but a HEAD exists.
        return GitChangeBrief(comparable=False, head="h0", commit_count=0)

    RecordGitHistoryUseCase(_WSRepo2(), watch_repo, provider).execute(
        RecordGitHistoryInput(workspace_id="w1")
    )
    assert watch_repo.get_history_cursor("w1") == "h0"
    assert watch_repo.list_history("w1") == []
