"""Propose candidate profile facts from text — review-first.

The local model reads a conversation (or any text you paste about yourself) and
*suggests* durable facts about you. It never saves anything: the candidates are
returned for you to approve one by one. This keeps memory honest — the model can
help, but you decide what is remembered.

The prompt and the parser are pure and deterministic here; only the model call in
the use case is non-deterministic, and its output is strictly validated.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.user_profile import CATEGORIES, UserProfileCategory, normalize


@dataclass(frozen=True)
class CandidateFact:
    category: str
    text: str


_DELIM = "|"


def build_extraction_prompt(text: str, max_facts: int = 6) -> str:
    """Ask the model for durable, user-about facts only — not project facts,
    not secrets, not one-off requests."""
    snippet = text.strip()[:6000]
    categories = ", ".join(CATEGORIES)
    return (
        "You extract durable facts about the PERSON from the text below, to "
        "personalise future answers. Only facts about the user themselves: their "
        "role, how they like answers, their language/tone, and stable context "
        "(team conventions, the stack they work with).\n\n"
        "Strict rules:\n"
        "- Only what is clearly about the user, stated or strongly implied.\n"
        "- NO secrets, credentials, tokens, or personal contact details.\n"
        "- NO one-off or task-specific requests (e.g. 'summarise this file').\n"
        "- NO facts about the project itself (those are remembered separately).\n"
        f"- At most {max_facts} facts. If there is nothing durable, output nothing.\n\n"
        f"Output one fact per line as: category{_DELIM}fact\n"
        f"where category is one of: {categories}\n"
        "Keep each fact short and in plain language. No numbering, no extra prose.\n\n"
        "Text:\n"
        f"{snippet}\n"
    )


def parse_candidates(
    raw: str,
    existing_texts: list[str] | None = None,
    max_facts: int = 6,
) -> list[CandidateFact]:
    """Parse the model's ``category|fact`` lines into validated candidates.

    Drops malformed lines, unknown categories, empties, anything already in the
    profile, and any in-batch duplicates. Robust to the model adding stray prose.
    """
    existing = {normalize(t) for t in (existing_texts or [])}
    seen: set[str] = set()
    out: list[CandidateFact] = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-*•").strip()
        if _DELIM not in line:
            continue
        category, _, text = line.partition(_DELIM)
        category = category.strip().lower()
        text = " ".join(text.split())
        if category not in CATEGORIES:
            # Tolerate a model that omits/garbles the category — keep the fact.
            text = " ".join(f"{category} {text}".split()) if category else text
            category = UserProfileCategory.FACT
        if not text or len(text) > 600:
            continue
        norm = normalize(text)
        if norm in existing or norm in seen:
            continue
        seen.add(norm)
        out.append(CandidateFact(category=category, text=text))
        if len(out) >= max_facts:
            break
    return out
