"""Structure-aware text chunking for local RAG indexing.

The goal is retrieval quality: chunks should follow the natural structure of a
document (markdown headings, code blocks, config sections) instead of cutting
blindly every N characters. Splitting mid-line or mid-statement scatters meaning
across chunks and hurts both embedding quality and what the model finally reads.

Design (best-practice local RAG):

- Split the document into *logical units* first, based on file type:
  markdown by heading sections, code/config by blank-line-separated blocks.
- Greedily pack consecutive units into chunks up to ``max_chars``, never
  splitting a unit unless it alone exceeds the limit.
- Carry a small *line-based overlap* between consecutive chunks so context that
  spans a boundary is not lost.
- Merge a tiny trailing chunk back into its predecessor instead of emitting a
  fragment with no standalone meaning.
- Guarantee that any non-empty document yields at least one chunk and that no
  content is dropped.

``chunk_text`` keeps its original signature for backward compatibility;
``chunk_document`` is the structure-aware entry point used by indexing.
"""

import re

DEFAULT_CHUNK_MAX_CHARS = 1500
DEFAULT_CHUNK_OVERLAP_CHARS = 200
MIN_CHUNK_CHARS = 200

_HEADING_RE = re.compile(r"^#{1,6}\s")
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")

# File types (as detected by the project scanner) that are line/section oriented
# and chunk best on blank-line block boundaries rather than prose paragraphs.
_CODE_LIKE_TYPES = {
    "python",
    "shell",
    "terraform",
    "terragrunt",
    "yaml",
    "json",
    "docker",
    "gitlab_ci",
    "github_actions",
    "kubernetes",
    "helm",
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token)."""
    return max(1, len(text) // 4)


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Backward-compatible generic chunker (paragraph/line aware)."""
    _validate(max_chars, overlap)
    units = _split_generic(text)
    return _pack_units(units, max_chars, overlap)


def chunk_document(
    content: str,
    file_type: str | None = None,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Structure-aware chunker that adapts splitting to the document type."""
    _validate(max_chars, overlap)
    if file_type == "markdown":
        units = _split_markdown(content)
    elif file_type in _CODE_LIKE_TYPES:
        units = _split_blocks(content)
    else:
        units = _split_generic(content)
    return _pack_units(units, max_chars, overlap)


def _validate(max_chars: int, overlap: int) -> None:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap must be zero or greater")
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")


# --- structure-aware splitters -------------------------------------------------


def _split_markdown(content: str) -> list[str]:
    """Split markdown into sections, each starting at a heading line."""
    lines = content.split("\n")
    sections: list[str] = []
    current: list[str] = []
    for line in lines:
        if _HEADING_RE.match(line) and any(item.strip() for item in current):
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    cleaned = [section for section in sections if section.strip()]
    return cleaned or _non_empty(content)


def _split_blocks(content: str) -> list[str]:
    """Split code/config into blank-line-separated logical blocks."""
    blocks = [block for block in _BLANK_LINE_RE.split(content) if block.strip()]
    return blocks or _non_empty(content)


def _split_generic(content: str) -> list[str]:
    """Split prose into paragraphs, falling back to the whole text."""
    paragraphs = [para for para in _BLANK_LINE_RE.split(content) if para.strip()]
    return paragraphs or _non_empty(content)


def _non_empty(content: str) -> list[str]:
    stripped = content.strip()
    return [stripped] if stripped else []


# --- packing -------------------------------------------------------------------


def _pack_units(units: list[str], max_chars: int, overlap: int) -> list[str]:
    units = [unit.rstrip() for unit in units if unit.strip()]
    if not units:
        return []

    expanded: list[str] = []
    for unit in units:
        if len(unit) <= max_chars:
            expanded.append(unit)
        else:
            expanded.extend(_hard_split(unit, max_chars, overlap))

    chunks: list[str] = []
    current: list[str] = []
    for unit in expanded:
        if current and _joined_len(current + [unit]) > max_chars:
            chunks.append(_join(current))
            seed = _overlap_tail(current, overlap)
            current = seed + [unit]
            if _joined_len(current) > max_chars:
                current = [unit]
        else:
            current.append(unit)

    if current:
        tail = _join(current)
        if chunks and len(tail) < MIN_CHUNK_CHARS:
            merged = chunks[-1] + "\n" + tail
            if len(merged) <= max_chars + overlap:
                chunks[-1] = merged
            else:
                chunks.append(tail)
        else:
            chunks.append(tail)

    return [chunk for chunk in chunks if chunk]


def _hard_split(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split a single oversized unit: prefer line boundaries, then characters."""
    lines = text.split("\n")
    if len(lines) > 1:
        return _pack_units(lines, max_chars, overlap)

    step = max_chars - overlap if max_chars > overlap else max_chars
    pieces: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end == length:
            break
        start += step
    return pieces


def _overlap_tail(units: list[str], overlap: int) -> list[str]:
    if overlap <= 0:
        return []
    tail: list[str] = []
    total = 0
    for unit in reversed(units):
        addition = len(unit) + (1 if tail else 0)
        if tail and total + addition > overlap:
            break
        tail.insert(0, unit)
        total += addition
    # Never let the overlap seed swallow the entire previous chunk.
    if len(tail) >= len(units) and tail:
        tail = tail[1:]
    return tail


def _join(units: list[str]) -> str:
    return "\n".join(units).strip()


def _joined_len(units: list[str]) -> int:
    return len("\n".join(units))
