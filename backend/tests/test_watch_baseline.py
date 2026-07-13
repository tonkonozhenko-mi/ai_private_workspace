""" "What changed while you were away" needs a *here* to measure from.

Until now the mark was only planted when someone pressed Refresh — which re-scans the
whole project — so a first session recorded nothing, and the second session could only
offer to start counting from then. The graph is already built by then; noting where the
project stands costs a read.
"""

from app.core.domain.project_graph import ProjectEntity, ProjectGraph, ProjectSnapshotMeta
from app.core.use_cases.run_project_watch import RunProjectWatchUseCase


class _Graphs:
    def __init__(self, graph: ProjectGraph | None, meta: ProjectSnapshotMeta | None):
        self._graph = graph
        self._meta = meta

    def get_latest_graph(self, workspace_id: str):  # noqa: ARG002
        return self._graph

    def get_latest_snapshot_meta(self, workspace_id: str):  # noqa: ARG002
        return self._meta


class _Watch:
    def __init__(self, digest: dict | None = None):
        self.digest = digest
        self.saves = 0

    def get_latest_digest(self, workspace_id: str):  # noqa: ARG002
        return self.digest

    def save_digest(self, workspace_id: str, digest: dict) -> None:  # noqa: ARG002
        self.digest = digest
        self.saves += 1


def _use_case(graphs: _Graphs, watch: _Watch) -> RunProjectWatchUseCase:
    def _never_rebuild(workspace_id: str):  # noqa: ARG001
        raise AssertionError("a baseline must not re-scan or rebuild anything")

    return RunProjectWatchUseCase(
        project_graph_repository=graphs,
        watch_repository=watch,
        build_graph=_never_rebuild,
    )


def _graph() -> tuple[ProjectGraph, ProjectSnapshotMeta]:
    graph = ProjectGraph(
        workspace_id="w",
        entities=[ProjectEntity(id="e1", type="service", name="api", analyzer="test")],
    )
    meta = ProjectSnapshotMeta(
        id="s1",
        workspace_id="w",
        created_at="2026-07-13T00:00:00Z",
        entity_count=1,
        relation_count=0,
        finding_count=0,
        analyzers_run=["test"],
        analyzers_skipped=[],
        scan_signature="sig",
    )
    return graph, meta


def test_the_first_look_plants_the_mark_the_next_one_measures_from():
    graph, meta = _graph()
    watch = _Watch()
    digest = _use_case(_Graphs(graph, meta), watch).ensure_baseline("w")

    assert digest is not None
    assert "Baseline recorded" in digest["summary"]
    assert watch.saves == 1


def test_a_baseline_never_overwrites_a_history_that_already_exists():
    """The mark is planted once. Re-planting it would erase what changed since."""
    graph, meta = _graph()
    watch = _Watch(digest={"summary": "3 things changed since the last check."})
    assert _use_case(_Graphs(graph, meta), watch).ensure_baseline("w") is None
    assert watch.saves == 0


def test_with_no_map_there_is_nothing_to_baseline_and_we_say_so_by_doing_nothing():
    watch = _Watch()
    assert _use_case(_Graphs(None, None), watch).ensure_baseline("w") is None
    assert watch.saves == 0
