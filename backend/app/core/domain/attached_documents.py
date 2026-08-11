"""Lexical selection of the most relevant excerpts from user-attached files.

When a user drops a log/config/source file into Ask, dumping the whole file into
the prompt can blow past the local model's context window. Instead we search the
file for the parts most relevant to the question and include only those, with a
strict character budget. Small files are included whole. The scoring is purely
lexical (term overlap) so it is instant, fully local, and needs no embeddings —
which works well for the keyword-rich files people attach (logs, configs, code).
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AttachedDocument:
    name: str
    content: str


_STOPWORDS = {
    "the",
    "and",
    "for",
    "are",
    "but",
    "not",
    "you",
    "your",
    "with",
    "this",
    "that",
    "have",
    "has",
    "was",
    "were",
    "what",
    "why",
    "how",
    "does",
    "did",
    "can",
    "from",
    "into",
    "out",
    "all",
    "any",
    "some",
    "when",
    "where",
    "which",
    "who",
    "will",
    "would",
    "should",
    "could",
    "about",
    "there",
    "their",
    "them",
    "then",
    "than",
    "they",
    "its",
    "it's",
    "is",
    "in",
    "on",
    "of",
    "to",
    "a",
    "an",
}

# Per-document and overall character budgets keep the prompt bounded.
#
# These were a third of their present size, on the assumption that an attachment
# is one more piece of evidence beside the project's own sources. That is not
# what people do with it: they attach a questionnaire and then talk about the
# questionnaire. At 4,000 characters a 120 KB document arrived as its first three
# per cent — enough to answer about its first two questions and nothing after,
# which is exactly how it failed live. A file someone chose to attach outranks
# chunks a search picked out on its behalf, so it gets the larger share.
# A document someone attached is the subject of the conversation, not a
# supporting quotation, so it arrives whole whenever it fits — which, at the
# 40,000 characters an attachment is capped at on the way in, it usually does.
# Selecting excerpts from it is the fallback, not the plan: excerpting can only
# guess which part the next question is about, and a follow-up like "and the
# third one?" carries nothing to guess with.
INCLUDE_WHOLE_THRESHOLD = 40_000
# When a document is longer than that, these bound the excerpting instead.
PER_DOCUMENT_BUDGET = 12_000
TOTAL_BUDGET = 48_000
CHUNK_TARGET_CHARS = 1_000


def _question_terms(question: str) -> set[str]:
    """The words in the question worth matching a document against.

    `\w` rather than `[A-Za-z0-9_]`: the old pattern matched Latin letters only,
    so a question written in Ukrainian, Greek or Japanese produced no
    terms at all. Not "few terms" — none. Every chunk then scored zero, the
    selector fell through to its no-keyword-match branch, and the document
    arrived as its first few thousand characters no matter what was asked. The
    app has an answer-language directive and a Cyrillic-speaking author; this
    was one regex away from working.
    """
    tokens = re.findall(r"\w+", question.lower())
    return {token for token in tokens if len(token) >= 3 and token not in _STOPWORDS}


def _chunk_by_lines(content: str) -> list[tuple[int, int, str]]:
    """Split content into ~CHUNK_TARGET_CHARS windows aligned to line breaks.

    Returns tuples of (start_line, end_line, text) with 1-based line numbers.
    """
    lines = content.splitlines()
    chunks: list[tuple[int, int, str]] = []
    buffer: list[str] = []
    buffer_len = 0
    start_line = 1
    for index, line in enumerate(lines, start=1):
        buffer.append(line)
        buffer_len += len(line) + 1
        if buffer_len >= CHUNK_TARGET_CHARS:
            chunks.append((start_line, index, "\n".join(buffer)))
            buffer = []
            buffer_len = 0
            start_line = index + 1
    if buffer:
        chunks.append((start_line, len(lines), "\n".join(buffer)))
    return chunks


def _score_chunk(text: str, terms: set[str]) -> int:
    if not terms:
        return 0
    lowered = text.lower()
    # Unicode, for the same reason as _question_terms: the document is as likely
    # to be in Cyrillic as the question. Both halves of a comparison have to
    # speak the same alphabet, and one of them not doing so is invisible —
    # nothing fails, the score is merely always zero.
    found = re.findall(r"\w+", lowered)
    counts: dict[str, int] = {}
    for token in found:
        if token in terms:
            counts[token] = counts.get(token, 0) + 1
    # Frequency (capped per term) plus a bonus for covering distinct terms.
    frequency = sum(min(count, 3) for count in counts.values())
    distinct_bonus = 2 * len(counts)
    return frequency + distinct_bonus


def _spread_sample(document: AttachedDocument, chunks: list[tuple[int, int, str]]) -> str:
    """Evenly spaced windows covering the whole document, within budget.

    Used when nothing in the question matches anything in the document. Reading
    the beginning is a guess about where the answer lives; reading a spread is
    an admission that we do not know.
    """
    if not chunks:
        return ""
    affordable = max(1, PER_DOCUMENT_BUDGET // max(1, len(chunks[0][2])))
    if affordable >= len(chunks):
        picked = chunks
    else:
        step = len(chunks) / affordable
        picked = [chunks[min(len(chunks) - 1, int(index * step))] for index in range(affordable)]
    pieces = [
        f"--- {document.name} (lines {start}-{end}; sampled across the document) ---\n{text}"
        for start, end, text in picked
    ]
    return "\n\n".join(pieces)


def _select_document_excerpt(document: AttachedDocument, terms: set[str]) -> str:
    content = document.content.strip("\n")
    if not content.strip():
        return ""
    if len(content) <= INCLUDE_WHOLE_THRESHOLD:
        return f"--- {document.name} (full file) ---\n{content}"

    chunks = _chunk_by_lines(content)
    scored = [
        (index, start, end, text, _score_chunk(text, terms))
        for index, (start, end, text) in enumerate(chunks)
    ]
    relevant = [item for item in scored if item[4] > 0]
    if not relevant:
        # Nothing matched. Taking the head of the file was the old answer, and it
        # is the wrong one whenever the question and the document are in
        # different languages — which is the normal case here: an English
        # questionnaire, a question in Ukrainian. No word can overlap, so the
        # "match" never happens, and the person gets the opening pages whatever
        # they asked. Question one is there; question three is not.
        #
        # A spread of windows across the whole file gives every part a chance,
        # and the locator says plainly that this is a sample rather than the
        # document.
        return _spread_sample(document, chunks)

    # Highest scoring first, then restore reading order for the kept chunks.
    relevant.sort(key=lambda item: (-item[4], item[0]))
    kept: list[tuple[int, int, int, str]] = []
    used = 0
    for index, start, end, text, _score in relevant:
        if used + len(text) > PER_DOCUMENT_BUDGET and kept:
            break
        kept.append((index, start, end, text))
        used += len(text)
    kept.sort(key=lambda item: item[0])

    pieces = [
        f"--- {document.name} (lines {start}-{end}) ---\n{text}"
        for _index, start, end, text in kept
    ]
    return "\n\n".join(pieces)


def build_attached_documents_section(
    question: str,
    documents: list[AttachedDocument] | None,
) -> str:
    """Return a prompt section with the most relevant excerpts, or '' if none."""
    if not documents:
        return ""

    terms = _question_terms(question)
    excerpts: list[str] = []
    total = 0
    for document in documents:
        excerpt = _select_document_excerpt(document, terms)
        if not excerpt:
            continue
        if total + len(excerpt) > TOTAL_BUDGET and excerpts:
            break
        excerpts.append(excerpt)
        total += len(excerpt)

    if not excerpts:
        return ""

    body = "\n\n".join(excerpts)
    return (
        "Attached files (provided by the user for THIS question; treat as evidence "
        "and cite by file name):\n"
        f"{body}\n\n"
    )
