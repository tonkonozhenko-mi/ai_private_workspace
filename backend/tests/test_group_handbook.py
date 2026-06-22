"""Group handbook builder (pure) + storage use case + Ask group-memory context."""

from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.core.domain.group_handbook import build_group_handbook
from app.core.domain.group_overview import (
    GroupMemberOverview,
    GroupMemberRisk,
    GroupOverview,
)
from app.core.domain.project_group import ProjectGroup
from app.core.domain.project_memory import MemoryKind
from app.core.use_cases.build_group_handbook import BuildGroupHandbookUseCase


def _overview() -> GroupOverview:
    return GroupOverview(
        group_id="g1",
        name="Platform",
        member_count=2,
        totals={"services": 3, "commits_last_7_days": 12, "repos": 2},
        environments=["dev", "prod"],
        technologies=["Helm", "Terraform"],
        risks=[GroupMemberRisk("w1", "api", "high", "No remote state")],
        members=[
            GroupMemberOverview(
                workspace_id="w1", name="api", project_path="/p/w1", built=True,
                indexed=True, description="3 service(s); 2 env(s): dev, prod",
            ),
            GroupMemberOverview(
                workspace_id="w2", name="web", project_path="/p/w2", built=False,
                indexed=False, description="Not analyzed yet.",
            ),
        ],
    )


def test_build_group_handbook_is_deterministic_and_covers_sections():
    text = build_group_handbook(_overview())
    assert "# Platform — group handbook" in text
    assert "## Repositories" in text and "**api**" in text and "**web**" in text
    assert "## Environments" in text and "dev, prod" in text
    assert "## Technologies" in text and "Helm, Terraform" in text
    assert "## Risks worth a look" in text and "[high] No remote state (api)" in text
    assert "## Where to start" in text
    # Deterministic: same input -> identical output.
    assert build_group_handbook(_overview()) == text


class _FakeOverviewUseCase:
    def execute(self, group_id):
        return _overview()


def test_handbook_use_case_stores_singleton_under_group_id():
    memory = InMemoryProjectMemoryRepository()
    uc = BuildGroupHandbookUseCase(_FakeOverviewUseCase(), memory)
    uc.execute("g1")
    uc.execute("g1")  # regenerate — must remain a singleton
    items = memory.list("g1")
    handbooks = [i for i in items if i.kind == MemoryKind.HANDBOOK]
    assert len(handbooks) == 1
    assert handbooks[0].workspace_id == "g1" and handbooks[0].pinned


def test_group_memory_is_separate_from_member_memory():
    memory = InMemoryProjectMemoryRepository()
    groups = InMemoryProjectGroupRepository()
    groups.add(ProjectGroup(id="g1", name="P", workspace_ids=("w1",), created_at="2026-06-01"))
    BuildGroupHandbookUseCase(_FakeOverviewUseCase(), memory).execute("g1")
    # Stored under the group id, not under any member workspace id.
    assert memory.list("g1")
    assert memory.list("w1") == []
