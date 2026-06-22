"""Project group domain + repository + manage use case (pure / in-memory)."""

from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.core.domain.project_group import (
    ProjectGroup,
    add_member,
    remove_member,
    rename_group,
    set_members,
)
from app.core.use_cases.manage_project_groups import (
    ManageProjectGroupsUseCase,
    ProjectGroupNotFoundError,
    ProjectGroupValidationError,
)


def _group(**kw) -> ProjectGroup:
    base = dict(id="g1", name="Platform", workspace_ids=(), created_at="2026-06-01")
    base.update(kw)
    return ProjectGroup(**base)


def test_add_member_keeps_order_and_dedupes():
    g = _group()
    g = add_member(g, "a")
    g = add_member(g, "b")
    g = add_member(g, "a")  # duplicate ignored
    assert g.workspace_ids == ("a", "b")
    assert g.member_count == 2


def test_remove_member():
    g = _group(workspace_ids=("a", "b", "c"))
    assert remove_member(g, "b").workspace_ids == ("a", "c")
    assert remove_member(g, "zzz").workspace_ids == ("a", "b", "c")  # no-op


def test_set_members_dedupes_preserving_order():
    g = _group()
    g = set_members(g, ["b", "a", "b", "", "c"])
    assert g.workspace_ids == ("b", "a", "c")


def test_rename_ignores_blank():
    g = _group()
    assert rename_group(g, "  ").name == "Platform"
    assert rename_group(g, "  New ").name == "New"


def test_usecase_create_list_get():
    repo = InMemoryProjectGroupRepository()
    uc = ManageProjectGroupsUseCase(repo)
    created = uc.create("Billing", ["w1", "w2", "w1"])
    assert created.workspace_ids == ("w1", "w2")
    assert created.id and created.created_at
    listed = uc.list()
    assert len(listed) == 1 and listed[0].id == created.id
    assert uc.get(created.id).name == "Billing"


def test_usecase_create_requires_name():
    uc = ManageProjectGroupsUseCase(InMemoryProjectGroupRepository())
    try:
        uc.create("   ")
        raise AssertionError("expected validation error")
    except ProjectGroupValidationError:
        pass


def test_usecase_membership_edits_persist():
    repo = InMemoryProjectGroupRepository()
    uc = ManageProjectGroupsUseCase(repo)
    g = uc.create("Group")
    uc.add_member(g.id, "w1")
    uc.add_member(g.id, "w2")
    uc.remove_member(g.id, "w1")
    assert repo.get(g.id).workspace_ids == ("w2",)
    uc.set_members(g.id, ["x", "y"])
    assert repo.get(g.id).workspace_ids == ("x", "y")


def test_usecase_get_missing_raises():
    uc = ManageProjectGroupsUseCase(InMemoryProjectGroupRepository())
    try:
        uc.get("nope")
        raise AssertionError("expected not found")
    except ProjectGroupNotFoundError:
        pass


def test_usecase_delete():
    repo = InMemoryProjectGroupRepository()
    uc = ManageProjectGroupsUseCase(repo)
    g = uc.create("Group")
    uc.delete(g.id)
    assert repo.get(g.id) is None
