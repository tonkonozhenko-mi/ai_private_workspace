"""User profile: durable, local facts about the *person* using the app.

Where Project Memory remembers a project, this remembers **you** — across every
workspace. Small, stable facts and preferences ("I'm a DevOps engineer", "answer
in Russian", "keep it concise", "we call production 'prd'") that shape how every
answer is written, in Ask and the Investigator alike.

It is deliberately simple and honest: the facts are plain text the user can see,
edit, pin, and delete; selection for a prompt is pinned + keyword + recency, not
an LLM guess; and the store is local — nothing about the user leaves the machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class UserProfileCategory:
    """What kind of thing a profile fact is — drives the label only."""

    ROLE = "role"  # who they are (DevOps engineer, backend dev…)
    PREFERENCE = "preference"  # how they want answers (concise, examples…)
    STYLE = "style"  # tone / language
    CONTEXT = "context"  # ongoing situation (team, stack, conventions)
    FACT = "fact"  # any other durable fact


CATEGORIES = (
    UserProfileCategory.ROLE,
    UserProfileCategory.PREFERENCE,
    UserProfileCategory.STYLE,
    UserProfileCategory.CONTEXT,
    UserProfileCategory.FACT,
)

_CATEGORY_LABELS = {
    UserProfileCategory.ROLE: "Role",
    UserProfileCategory.PREFERENCE: "Preference",
    UserProfileCategory.STYLE: "Style",
    UserProfileCategory.CONTEXT: "Context",
    UserProfileCategory.FACT: "Fact",
}


@dataclass(frozen=True)
class UserProfileItem:
    id: str
    category: str
    text: str
    created_at: str  # ISO 8601
    pinned: bool = False


_WORD_RE = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2}


def normalize(text: str) -> str:
    """Whitespace/case-normalised form, for de-duplication."""
    return " ".join(text.lower().split())


def is_duplicate(items: list[UserProfileItem], text: str) -> bool:
    """True if a fact with the same normalised text already exists — so adding
    the same thing twice quietly no-ops instead of piling up."""
    norm = normalize(text)
    return any(normalize(i.text) == norm for i in items)


def select_for_prompt(
    items: list[UserProfileItem],
    query: str = "",
    limit: int = 8,
) -> list[UserProfileItem]:
    """Which facts to apply to an answer: pinned first, then keyword overlap with
    the question, then recency. With no query, the most recent (pinned-first) win.

    The profile is small and stable, so this is generous on purpose — most
    projects will have only a handful of facts and all of them are relevant.
    """
    query_tokens = _tokens(query)

    def score(item: UserProfileItem) -> tuple:
        overlap = len(_tokens(item.text) & query_tokens) if query_tokens else 0
        return (1 if item.pinned else 0, overlap, item.created_at)

    return sorted(items, key=score, reverse=True)[:limit]


def format_user_profile_context(items: list[UserProfileItem], max_chars: int = 900) -> str:
    """A compact block describing the user, to prepend to a prompt. Framed so the
    model applies it to *how* it answers, not as project fact."""
    if not items:
        return ""
    lines: list[str] = []
    used = 0
    for item in items:
        label = _CATEGORY_LABELS.get(item.category, "Fact")
        text = " ".join(item.text.split())
        line = f"- {label}: {text}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    if not lines:
        return ""
    return (
        "About the person you are helping (apply this to tone, language, focus and "
        "assumptions; it is not a fact about the project):\n" + "\n".join(lines)
    )
