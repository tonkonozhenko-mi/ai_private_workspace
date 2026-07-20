"""Noticing when a model has stopped writing and started looping.

Maks, 16.07: Mistral wrote a good answer and then repeated the same paragraph
about ten times. He pressed Stop, so the answer was lost — but nothing in the app
had noticed, and left alone it would have looped until the token limit ran out,
spending minutes of his machine to produce a wall of one paragraph.

This is not a bug in the model so much as a known failure mode of small ones:
with a low temperature and no penalty for repeating itself, greedy decoding can
fall into a cycle it has no reason to leave. The first defence is to ask the
engine not to (a repetition penalty, which we were not sending at all). This is
the second: watch what actually arrives, and stop when it starts going round.

Kept blunt on purpose. A real answer repeats short things all the time — a
heading, a file path, "Yes." — so only a substantial paragraph, seen three times,
counts. The cost of being wrong here is truncating an answer someone wanted,
which is why the bar is high and the unit is a paragraph rather than a line.
"""

from __future__ import annotations

# Below this, repetition is ordinary prose: bullets, paths, short confirmations.
MIN_PARAGRAPH_CHARS = 80
# Twice can be emphasis or a genuine restatement. Three times is a loop.
REPEATS_BEFORE_LOOPING = 3


def looping_paragraph(text: str) -> str | None:
    """The paragraph this answer has got stuck on, or None if it is still
    writing. Whitespace is normalised so an extra blank line does not hide it."""
    seen: dict[str, int] = {}
    for block in text.split("\n\n"):
        paragraph = " ".join(block.split())
        if len(paragraph) < MIN_PARAGRAPH_CHARS:
            continue
        seen[paragraph] = seen.get(paragraph, 0) + 1
        if seen[paragraph] >= REPEATS_BEFORE_LOOPING:
            return paragraph
    return None


def trim_to_first_loop(text: str) -> str:
    """The answer with the repetition cut off, keeping the first occurrence.

    What the model said once is still what it said; what it said for the third
    time is the loop, and everything after it is the same loop continuing.
    """
    paragraph = looping_paragraph(text)
    if paragraph is None:
        return text
    blocks = text.split("\n\n")
    kept: list[str] = []
    times = 0
    for block in blocks:
        if " ".join(block.split()) == paragraph:
            times += 1
            if times > 1:
                break
        kept.append(block)
    return "\n\n".join(kept).rstrip()
