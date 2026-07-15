"""What the model is told about the conversation so far.

A follow-up is the point of a conversation: "and where is that configured?" has
no subject of its own. The single Ask learned to carry the thread — read the
turns, budget them against the model's window, fold the evicted ones into a
summary, and prepend the last questions to the retrieval query so search lands on
what "that" refers to.

The group Ask needed the same thing, and the choice was to copy those four
methods or to move them somewhere both could call. Copies diverge — that is the
whole story of the group path, which spent three releases quietly missing fixes
the single path had. So they live here, as plain functions over an injected
repository, and neither use case owns them.

The scope id is opaque: a workspace id from one caller, a group id from the
other. The conversation store never looked at it — no foreign key, no
validation, just string equality — and the project-memory store has been keyed by
group ids the same way since groups existed.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.domain.conversation_budget import (
    SUMMARY_TRIGGER_MIN_OLDER_TURNS,
    history_token_budget,
    split_history_by_budget,
)

Turn = tuple[str, str]
# How many of the previous questions carry enough subject to steer retrieval. Two:
# enough to resolve "it" through a follow-up of a follow-up, few enough that an
# old topic doesn't drag the search back to itself.
_RETRIEVAL_HISTORY_TURNS = 2


def conversation_turns(repository, scope_id: str, conversation_id: str | None) -> list[Turn]:
    """Every (role, content) user/assistant turn of one conversation.

    Best-effort by design: a missing repository, a missing conversation or any
    error yields no history, so answering never depends on remembering.
    """
    if repository is None or not conversation_id:
        return []
    try:
        conversation = repository.get_conversation(scope_id, conversation_id)
    except Exception:  # noqa: BLE001 - history is optional, never fail the ask
        return []
    if conversation is None:
        return []
    return [
        (message.role, message.content)
        for message in conversation.messages
        if message.role in ("user", "assistant") and message.content.strip()
    ]


def recent_turns(turns: list[Turn]) -> list[Turn]:
    """The turns that fit a default budget — used to steer retrieval, where the
    model's real window is not the constraint."""
    _older, recent = split_history_by_budget(turns, history_token_budget(None))
    return recent


def history_for_prompt(
    turns: list[Turn],
    context_window: int | None,
    summarize: Callable[[list[Turn]], str],
) -> list[Turn]:
    """The history actually sent to the model: recent turns that fit the window's
    history budget, with the older evicted ones folded into one short summary so
    the thread isn't lost after a few exchanges.

    ``summarize`` is injected (it costs a model call) and is only asked when
    enough turns were evicted to be worth it; any failure degrades to the recent
    turns, which is the behaviour before summaries existed.
    """
    if not turns:
        return []
    older, recent = split_history_by_budget(turns, history_token_budget(context_window))
    if len(older) < SUMMARY_TRIGGER_MIN_OLDER_TURNS:
        return recent
    summary = summarize(older)
    if not summary:
        return recent
    preface = f"[Summary of the earlier conversation — context only, not a new question]\n{summary}"
    return [("user", preface), *recent]


def retrieval_query_with_history(question: str, turns: list[Turn]) -> str:
    """The text to search with, expanded by what the conversation was about.

    "How do I disable it?" has no searchable subject on its own, so retrieval
    would miss the very files the conversation is about. The previous questions
    carry the real terms; they steer the search and are never shown to the model
    as part of the question.
    """
    prior = [content for role, content in turns if role == "user" and content.strip()]
    prior = prior[-_RETRIEVAL_HISTORY_TURNS:]
    if not prior:
        return question
    return "\n".join([*prior, question])
