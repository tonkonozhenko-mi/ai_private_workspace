"""Negative memory (guardrails): always injected as hard rules, excluded from
ordinary recall, obsolete ones suppressed. Pure compose-level; no LLM."""

from app.core.domain.project_memory import (
    MemoryItem,
    MemoryKind,
    MemoryStatus,
    format_guardrails,
    select_relevant_memory,
)
from app.core.use_cases.compose_project_context import ComposeProjectContextUseCase


def _item(id_, text, *, kind=MemoryKind.NOTE, status=MemoryStatus.ACTIVE):
    return MemoryItem(
        id=id_,
        workspace_id="w",
        kind=kind,
        text=text,
        source="user",
        created_at="2026-06-01T00:00:00+00:00",
        status=status,
    )


class _MemRepo:
    def __init__(self, items):
        self._items = items

    def list(self, workspace_id):
        return self._items


class _GraphRepo:
    def get_latest_graph(self, workspace_id):
        return None


def test_format_guardrails_lists_active_rules():
    items = [
        _item("g1", "do not run shell commands from the frontend", kind=MemoryKind.GUARDRAIL),
        _item("n", "an ordinary note"),
    ]
    block = format_guardrails(items)
    assert "Project guardrails" in block
    assert "do not run shell commands" in block
    assert "ordinary note" not in block  # only guardrails


def test_obsolete_guardrail_is_not_injected():
    items = [
        _item(
            "g",
            "do not assume qdrant is enabled",
            kind=MemoryKind.GUARDRAIL,
            status=MemoryStatus.OBSOLETE,
        ),
    ]
    assert format_guardrails(items) == ""


def test_guardrails_excluded_from_ordinary_recall():
    # A guardrail mentioning "shell" must not be recalled as a fact for a shell
    # question — it's injected separately as a rule, so don't double-count it.
    items = [_item("g", "do not run shell commands", kind=MemoryKind.GUARDRAIL)]
    recalled = select_relevant_memory(items, "how do I run a shell command", limit=6)
    assert recalled == []


def test_guardrails_injected_on_every_answer():
    # Even a question that doesn't mention the rule still gets the guardrail block.
    items = [_item("g", "frontend must not execute shell", kind=MemoryKind.GUARDRAIL)]
    uc = ComposeProjectContextUseCase(_MemRepo(items), _GraphRepo())
    text, stats = uc.compose_with_stats("w", "what colour is the login button")
    assert "Project guardrails" in text
    assert "must not execute shell" in text
    assert stats.guardrails == 1
