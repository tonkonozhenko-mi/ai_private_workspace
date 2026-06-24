"""Token-budgeted conversation history with rolling summarization.

Previously Ask kept a fixed number of recent turns (``turns[-6:]``): six long
turns could overflow the window, six short ones wasted room, and anything older
was simply forgotten. This module instead keeps as many *recent* turns as fit a
token budget, and folds the *older* evicted turns into a short running summary so
the thread isn't lost after a few exchanges.

Everything here is pure (token counts estimated at ~4 chars/token); the actual
summary text is produced by the caller's local model via ``build_summary_prompt``.
"""

from __future__ import annotations

CHARS_PER_TOKEN = 4
# Cap how much of the window history may consume, so chunks/memory keep room.
DEFAULT_HISTORY_TOKEN_BUDGET = 1500
# Don't spend a model call summarizing one stray evicted turn.
SUMMARY_TRIGGER_MIN_OLDER_TURNS = 2
# Per-turn text cap when feeding turns to the summarizer.
_SUMMARY_TURN_CHARS = 600

Turn = tuple[str, str]  # (role, content)


def estimate_turn_tokens(content: str) -> int:
    return len(content) // CHARS_PER_TOKEN if content else 0


def history_token_budget(context_window: int | None) -> int:
    """How many tokens of history we allow, given the model window."""
    window = context_window if (context_window and context_window > 0) else 8192
    return max(256, min(DEFAULT_HISTORY_TOKEN_BUDGET, window // 4))


def split_history_by_budget(
    turns: list[Turn],
    token_budget: int,
) -> tuple[list[Turn], list[Turn]]:
    """Split ``turns`` into ``(older, recent)``: the most recent turns whose
    cumulative size fits ``token_budget`` are ``recent`` (order preserved); the
    earlier turns are ``older`` (candidates for summarization). At least the last
    turn is always kept."""
    kept: list[Turn] = []
    used = 0
    for role, content in reversed(turns):
        cost = estimate_turn_tokens(content)
        if kept and used + cost > token_budget:
            break
        kept.append((role, content))
        used += cost
    kept.reverse()
    older = turns[: len(turns) - len(kept)]
    return older, kept


def build_summary_prompt(older_turns: list[Turn]) -> str:
    """A prompt asking the local model to compress the earlier turns into a few
    plain sentences the later prompt can carry as context."""
    lines = [
        "Summarize the earlier part of this conversation in 2-4 short sentences, "
        "capturing what the user is working on, the key facts established, and any "
        "decisions or corrections. Write plain prose, no preamble.",
        "",
        "Conversation so far:",
    ]
    for role, content in older_turns:
        speaker = "User" if role == "user" else "Assistant"
        text = " ".join(content.split())[:_SUMMARY_TURN_CHARS]
        if text:
            lines.append(f"{speaker}: {text}")
    lines.append("")
    lines.append("Summary:")
    return "\n".join(lines)
