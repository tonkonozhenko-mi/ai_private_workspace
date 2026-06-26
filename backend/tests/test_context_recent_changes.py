"""The dated change journal is injected into Ask context for change questions."""

from app.adapters.memory.in_memory_project_graph_repository import (
    InMemoryProjectGraphRepository,
)
from app.adapters.memory.in_memory_project_watch_repository import (
    InMemoryProjectWatchRepository,
)
from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.core.use_cases.compose_project_context import ComposeProjectContextUseCase


def _composer():
    watch = InMemoryProjectWatchRepository()
    watch.append_history(
        "w1",
        {
            "checked_at": "2026-06-26T10:00:00+00:00",
            "summary": "13 commits by the team",
            "llm_summary": "Updated the VPN ASN and CloudFront access control.",
            "commit_subjects": ["fix vpn asn", "add cloudfront geo restriction"],
        },
    )
    composer = ComposeProjectContextUseCase(
        InMemoryProjectMemoryRepository(),
        InMemoryProjectGraphRepository(),
        watch_repository=watch,
    )
    return composer


def test_change_question_includes_recent_changes():
    ctx, stats = _composer().compose_with_stats("w1", "what changed today?")
    assert "Recent project changes" in ctx
    assert "VPN ASN" in ctx
    assert stats.recent_changes == 1


def test_non_change_question_omits_recent_changes():
    ctx, stats = _composer().compose_with_stats("w1", "how is the database configured?")
    assert "Recent project changes" not in ctx
    assert stats.recent_changes == 0


def test_ukrainian_change_question_triggers_journal():
    ctx, _ = _composer().compose_with_stats("w1", "що змінилось у проєкті?")
    assert "Recent project changes" in ctx


def test_no_watch_repo_is_safe():
    composer = ComposeProjectContextUseCase(
        InMemoryProjectMemoryRepository(), InMemoryProjectGraphRepository()
    )
    ctx, stats = composer.compose_with_stats("w1", "what changed today?")
    assert ctx == ""
    assert stats.recent_changes == 0
