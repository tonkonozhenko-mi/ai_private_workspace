"""A deleted workspace must not linger as a phantom group member."""

from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.core.use_cases.manage_project_groups import ManageProjectGroupsUseCase


def _use_case() -> ManageProjectGroupsUseCase:
    return ManageProjectGroupsUseCase(InMemoryProjectGroupRepository())


def test_prune_removes_workspace_from_every_group():
    uc = _use_case()
    g1 = uc.create("Group one", ["w1", "w2", "w3"])
    g2 = uc.create("Group two", ["w2"])
    assert g1.member_count == 3

    uc.prune_workspace("w2")

    assert uc.get(g1.id).workspace_ids == ("w1", "w3")
    assert uc.get(g1.id).member_count == 2
    # Removed from the second group too.
    assert uc.get(g2.id).member_count == 0


def test_prune_is_a_noop_when_workspace_not_in_any_group():
    uc = _use_case()
    g = uc.create("Group", ["w1"])
    uc.prune_workspace("unknown")
    assert uc.get(g.id).workspace_ids == ("w1",)
