"""Telling the standing rules apart from the thing actually being asked.

Maks pasted a page of NDA and anonymisation rules — placeholders, a document
inventory, a confidentiality checklist — meaning "write the onboarding docs, and
obey all this while you do it". He got the rules back, rephrased.

The app's part in that is specific and fixable. Whatever is in the box becomes
the search query, so 1,800 tokens of rules about `[PROJECT_NAME]` and
`[CLOUD_ACCOUNT_PROD]` went to the embedder, and the embedder — doing exactly its
job — found the documents most like a policy about confidentiality. The chunks
about how to deploy anything were nowhere near the top. Then those rules ate 28%
of the context window (measured: 1,792 of 6,516 tokens), so even the wrong chunks
arrived shortened.

Maks put it best: paste those same instructions to a person and they would write
the documentation. A person separates "what to do" from "how to behave while
doing it" without being asked. So the app does it too, mechanically:

    search with the request; prompt with everything.

The rules still reach the model in full — they are instructions and they must be
obeyed. They simply stop pretending to be a search query. Nothing is dropped,
nothing is rewritten, and when a message has no rule-like bulk in it (which is
almost every message) this changes nothing at all.
"""

from __future__ import annotations

import re

# Below this a message is a question, whatever it looks like, and splitting it
# would be a solution in search of a problem.
MIN_CHARS_TO_SPLIT = 1200

# A line that tells the assistant how to behave: a bullet, a heading, or a
# sentence in the imperative about form rather than about the project.
_RULE_LINE = re.compile(
    r"^\s*(?:[-*•]|\d+[.)])\s"                       # a bullet or numbered item
    r"|^\s*\[[A-Z_]+\]"                              # a placeholder, [PROJECT_NAME]
    r"|^\s*(?:do not|don't|never|always|use |replace |preserve |verify|ensure|"
    r"avoid|report |end the response|before |when |if complete|anonymi[sz]e)"
    r"|^\s*(?:не |никогда|всегда|используй|замени|убедись|проверь)"
    r"|^[A-Z][A-Za-z ,/]{2,60}:?\s*$",               # a bare heading line
    re.IGNORECASE,
)

# A line that asks for something to be produced. This is the request.
_ASK_LINE = re.compile(
    r"\b(?:составь|напиши|сделай|подготовь|создай|опиши|объясни|расскажи|"
    r"собери|сгенерируй|покажи|найди|"
    r"склади|напиши|зроби|підготуй|поясни|"
    r"write|create|make|prepare|draft|generate|compose|explain|describe|"
    r"summari[sz]e|list|show me|help me|what|where|how|why|which)\b",
    re.IGNORECASE,
)


def _is_rule(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    return bool(_RULE_LINE.match(text))


def split_instructions_from_request(message: str) -> tuple[str, str]:
    """Return ``(instructions, request)`` for a message.

    ``request`` is what to search with; ``instructions`` is everything else. When
    the message is short, or has no rule-like bulk, ``instructions`` is empty and
    ``request`` is the whole message — the common case, unchanged.

    A message that is *entirely* rules and asks for nothing keeps its whole text
    as the request. We do not know better than the person what they meant, and
    searching with nothing is worse than searching with everything.
    """
    text = message or ""
    if len(text) < MIN_CHARS_TO_SPLIT:
        return "", text

    lines = text.splitlines()
    rules: list[str] = []
    asks: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # An ask beats a rule: "Write the documentation in English" is both an
        # imperative and the request, and the request is what it is for.
        if _ASK_LINE.search(stripped) and not _is_rule(stripped):
            asks.append(stripped)
        else:
            # Everything that is not asking for something, in a message this
            # size, is telling the assistant how to behave. "The documentation
            # is confidential" states a condition, it does not name a subject to
            # search for — and searching for it finds documents about
            # confidentiality, which is exactly the failure being fixed.
            rules.append(stripped)

    rule_chars = sum(len(line) for line in rules)
    ask_chars = sum(len(line) for line in asks)
    # Only split when the rules genuinely dominate. A long question with a few
    # bullets in it is a long question.
    if rule_chars < ask_chars * 2:
        return "", text
    if not asks:
        return "", text

    return "\n".join(rules), "\n".join(asks)


def retrieval_text(message: str) -> str:
    """What to search the project with: the request, not the rulebook."""
    _instructions, request = split_instructions_from_request(message)
    return request
