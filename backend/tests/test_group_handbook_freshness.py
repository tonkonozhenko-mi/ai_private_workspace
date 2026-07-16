"""A group handbook knows what it was built from, and says when it is behind.

The handbook summarises every member repository. Re-index one member and the
summary is quietly out of date — still worth having, and no longer describing
what the app knows. So the handbook records each member's index timestamp when
it is written, and "is it behind?" becomes arithmetic on two sets of marks.

The point of the design is what is NOT here: no group-level change log, no
synchronisation, no watcher. A member's changes live in the member's workspace,
where a person switching to that project finds them exactly as they left them.
The group's only new state is a line of provenance on its own artifact.
"""

from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.core.domain.group_handbook_provenance import (
    format_index_snapshot,
    handbook_lag,
    has_index_snapshot,
    parse_index_snapshot,
)
from app.core.domain.group_overview import GroupOverview
from app.core.domain.project_group import ProjectGroup
from app.core.domain.project_memory import MemoryKind
from app.core.use_cases.build_group_handbook import (
    BuildGroupHandbookUseCase,
    GroupHandbookFreshnessUseCase,
)

WIKI = "ws-wiki"
CODE = "ws-code"
GROUP = "g1"

EARLY = "2026-07-15T09:00:00+00:00"
LATE = "2026-07-16T09:00:00+00:00"


class _Workspace:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _WorkspaceRepo:
    def get(self, workspace_id):
        return {WIKI: _Workspace(WIKI, "Wiki"), CODE: _Workspace(CODE, "Backend")}.get(
            workspace_id
        )


class _Status:
    def __init__(self, last_indexed_at):
        self.status = "indexed"
        self.last_indexed_at = last_indexed_at


class _StatusRepo:
    def __init__(self, marks):
        self.marks = dict(marks)

    def get(self, workspace_id):
        if workspace_id not in self.marks:
            return None
        return _Status(self.marks[workspace_id])


class _Overview:
    """Stands in for the aggregation; the handbook text is not what is under test."""

    def execute(self, group_id):
        return GroupOverview(group_id=group_id, name="Platform", member_count=2)


def _build(marks):
    groups = InMemoryProjectGroupRepository()
    groups.add(
        ProjectGroup(id=GROUP, name="Platform", workspace_ids=(WIKI, CODE), created_at=EARLY)
    )
    memory = InMemoryProjectMemoryRepository()
    statuses = _StatusRepo(marks)
    return groups, memory, statuses


def _write_handbook(groups, memory, statuses):
    return BuildGroupHandbookUseCase(
        _Overview(),
        memory,
        group_repository=groups,
        index_status_repository=statuses,
    )


def _freshness(groups, memory, statuses):
    return GroupHandbookFreshnessUseCase(
        memory_repository=memory,
        group_repository=groups,
        workspace_repository=_WorkspaceRepo(),
        index_status_repository=statuses,
    ).execute(GROUP)


# --- the snapshot, as arithmetic -----------------------------------------------


def test_a_snapshot_survives_being_written_down_and_read_back():
    marks = {WIKI: EARLY, CODE: None}
    line = format_index_snapshot(marks)

    assert has_index_snapshot(line)
    # A member with no index was not read, so it is not in the snapshot.
    assert parse_index_snapshot(line) == {WIKI: EARLY}


def test_a_member_that_was_reindexed_is_behind_the_snapshot():
    assert handbook_lag({WIKI: EARLY, CODE: EARLY}, {WIKI: LATE, CODE: EARLY}) == (WIKI,)


def test_a_member_that_has_not_moved_is_not_behind():
    assert handbook_lag({WIKI: EARLY, CODE: EARLY}, {WIKI: EARLY, CODE: EARLY}) == ()


def test_a_member_with_no_index_at_all_cannot_be_behind():
    assert handbook_lag({WIKI: EARLY}, {WIKI: EARLY, CODE: None}) == ()


def test_a_member_that_joined_after_the_build_is_behind():
    """The handbook has never heard of it — same lag, different route."""
    assert handbook_lag({WIKI: EARLY}, {WIKI: EARLY, CODE: LATE}) == (CODE,)


def test_a_handbook_with_no_snapshot_claims_nothing():
    assert has_index_snapshot(None) is False
    assert has_index_snapshot("Written by hand") is False
    assert parse_index_snapshot("Written by hand") == {}


# --- the same thing, through the use cases -------------------------------------


def test_the_handbook_records_what_it_read():
    groups, memory, statuses = _build({WIKI: EARLY, CODE: EARLY})
    _write_handbook(groups, memory, statuses).execute(GROUP)

    handbook = next(i for i in memory.list(GROUP) if i.kind == MemoryKind.HANDBOOK)
    assert parse_index_snapshot(handbook.grounding) == {WIKI: EARLY, CODE: EARLY}


def test_reindexing_one_member_puts_the_handbook_behind_it_by_name():
    groups, memory, statuses = _build({WIKI: EARLY, CODE: EARLY})
    _write_handbook(groups, memory, statuses).execute(GROUP)

    assert _freshness(groups, memory, statuses).stale_members == ()

    statuses.marks[WIKI] = LATE  # the wiki was re-indexed after the handbook

    freshness = _freshness(groups, memory, statuses)
    assert freshness.has_handbook is True
    assert freshness.stale_members == ("Wiki",)


def test_regenerating_makes_it_current_again():
    groups, memory, statuses = _build({WIKI: EARLY, CODE: EARLY})
    builder = _write_handbook(groups, memory, statuses)
    builder.execute(GROUP)
    statuses.marks[WIKI] = LATE
    assert _freshness(groups, memory, statuses).stale_members == ("Wiki",)

    builder.execute(GROUP)

    assert _freshness(groups, memory, statuses).stale_members == ()


def test_no_handbook_is_not_a_stale_handbook():
    groups, memory, statuses = _build({WIKI: EARLY})
    assert _freshness(groups, memory, statuses).has_handbook is False
    assert _freshness(groups, memory, statuses).stale_members == ()


def test_a_handbook_written_before_provenance_existed_is_not_nagged_about():
    """Not knowing what it read is not evidence that it is behind. Invariant: a
    group whose members have not changed looks exactly as it did."""
    groups, memory, statuses = _build({WIKI: EARLY, CODE: EARLY})
    # Built without the repositories wired — the old shape, no snapshot line.
    BuildGroupHandbookUseCase(_Overview(), memory).execute(GROUP)
    statuses.marks[WIKI] = LATE

    freshness = _freshness(groups, memory, statuses)
    assert freshness.has_handbook is True
    assert freshness.stale_members == ()
