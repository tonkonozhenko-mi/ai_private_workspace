"""The 'why' memory kinds: architecture decisions + past incident fixes."""

from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.core.domain.project_memory import (
    MemoryItem,
    MemoryKind,
    format_memory_context,
)
from app.core.use_cases.manage_project_memory import AddMemoryInput, AddMemoryUseCase


def _item(kind, text):
    return MemoryItem(
        id="i", workspace_id="w1", kind=kind, text=text, source="user", created_at="2026-01-01"
    )


def test_new_kinds_are_accepted_by_add_use_case():
    repo = InMemoryProjectMemoryRepository()
    uc = AddMemoryUseCase(repo)
    a = uc.execute(
        AddMemoryInput(
            workspace_id="w1",
            text="we use terragrunt because each env is a separate AWS account",
            kind=MemoryKind.ARCHITECTURE_DECISION,
        )
    )
    b = uc.execute(
        AddMemoryInput(
            workspace_id="w1",
            text="OOM in prod was fixed by raising the worker memory limit",
            kind=MemoryKind.INCIDENT_SOLUTION,
        )
    )
    assert a.kind == MemoryKind.ARCHITECTURE_DECISION
    assert b.kind == MemoryKind.INCIDENT_SOLUTION


def test_context_block_labels_the_why_kinds_distinctly():
    block = format_memory_context(
        [
            _item(MemoryKind.ARCHITECTURE_DECISION, "separate AWS account per env"),
            _item(MemoryKind.INCIDENT_SOLUTION, "raised worker memory"),
        ]
    )
    assert "Architecture decision (why):" in block
    assert "Past incident fix:" in block
