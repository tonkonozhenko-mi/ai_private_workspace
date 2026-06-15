"""Lexical selection of the most relevant excerpts from user-attached files.

When a user drops a log/config/source file into Ask, dumping the whole file into
the prompt can blow past the local model's context window. Instead we search the
file for the parts most relevant to the question and include only those, with a
strict character budget. Small files are included whole. The scoring is purely
lexical (term overlap) so it is instant, fully local, and needs no embeddings —
which works well for the keyword-rich files people attach (logs, configs, code).
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class AttachedDocument:
    name: str
    content: str


_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "your", "with", "this",
    "that", "have", "has", "was", "were", "what", "why", "how", "does", "did",
    "can", "from", "into", "out", "all", "any", "some", "when", "where", "which",
    "who", "will", "would", "should", "could", "about", "there", "their", "them",
    "then", "than", "they", "its", "it's", "is", "in", "on", "of", "to", "a", "an",
}

# Per-document and overall character budgets keep the prompt bounded.
INCLUDE_WHOLE_THRESHOLD = 4_000
PER_DOCUMENT_BUDGET = 4_000
TOTAL_BUDGET = 9_000
CHUNK_TARGET_CHARS = 1_000


def _question_terms(question: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+", question.lower())
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
    found = re.findall(r"[A-Za-z0-9_]+", lowered)
    counts: dict[str, int] = {}
    for token in found:
        if token in terms:
            counts[token] = counts.get(token, 0) + 1
    # Frequency (capped per term) plus a bonus for covering distinct terms.
    frequency = sum(min(count, 3) for count in counts.values())
    distinct_bonus = 2 * len(counts)
    return frequency + distinct_bonus


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
        # Nothing matched the question — fall back to the head of the file.
        head = content[:INCLUDE_WHOLE_THRESHOLD]
        return f"--- {document.name} (first {len(head)} chars; no keyword match) ---\n{head}"

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
