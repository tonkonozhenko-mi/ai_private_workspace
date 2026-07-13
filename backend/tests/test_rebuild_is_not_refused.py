"""A person pressing "rebuild" is not a cache miss to be argued with.

The map is cached against the files and the app version. A release that shipped under
the same version number was, to the cache, the same program — so after an update the map
on screen was still the one the old analyzers had built, and "Re-read the files" replied
"nothing changed" and left it there. Two things had to be true: the analyzers have a
version of their own, and an explicit click is an instruction, not a suggestion.
"""

from app.core.domain.project_graph_builder import ANALYZERS_VERSION
from app.core.use_cases.build_project_graph import (
    BuildProjectGraphInput,
    BuildProjectGraphUseCase,
)


class _Scan:
    def __init__(self):
        self.files = []


class _Scans:
    def get_latest_scan(self, workspace_id):  # noqa: ARG002
        return _Scan()


class _Workspaces:
    def get(self, workspace_id):  # noqa: ARG002
        class _W:
            project_path = "/tmp/project"
            assistant_mode = "devops"

        return _W()


class _Meta:
    def __init__(self, signature: str):
        self.scan_signature = signature
        self.id = "old"


class _Graphs:
    def __init__(self, signature: str):
        self.meta = _Meta(signature)
        self.saved = 0

    def get_latest_snapshot_meta(self, workspace_id):  # noqa: ARG002
        return self.meta

    def get_latest_graph(self, workspace_id):  # noqa: ARG002
        return None

    def save_graph(self, graph, scan_signature):  # noqa: ARG002
        self.saved += 1
        return _Meta(scan_signature)


def _use_case(graphs):
    return BuildProjectGraphUseCase(
        workspace_repository=_Workspaces(),
        project_scan_repository=_Scans(),
        file_system=None,
        project_graph_repository=graphs,
        git_history=None,
    )


def test_the_analyzers_have_a_version_of_their_own():
    """The app version alone let a release that only changed the analyzers slip past the
    cache, because the version number had not moved."""
    assert ANALYZERS_VERSION >= 2
    signature = BuildProjectGraphUseCase._scan_signature(_Scan())
    assert signature.startswith("sha256:")


def test_an_unchanged_project_is_not_re_analyzed_by_itself():
    """The cache still does its job when nobody asked for anything."""
    graphs = _Graphs(BuildProjectGraphUseCase._scan_signature(_Scan()))
    meta = _use_case(graphs).execute(BuildProjectGraphInput(workspace_id="w"))
    assert graphs.saved == 0
    assert meta.id == "old"


def test_but_a_person_who_asks_for_a_rebuild_gets_one():
    """Same files, same signature — and the analyzers run anyway, because someone asked.
    The cache exists to spare work nobody wanted, not to overrule the person."""
    graphs = _Graphs(BuildProjectGraphUseCase._scan_signature(_Scan()))
    _use_case(graphs).execute(BuildProjectGraphInput(workspace_id="w", force=True))
    assert graphs.saved == 1
