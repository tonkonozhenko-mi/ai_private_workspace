"""Structure-aware text chunking for local RAG indexing.

The goal is retrieval quality: chunks should follow the natural structure of a
file instead of cutting blindly every N characters. Splitting mid-function or
mid-statement scatters meaning across chunks and hurts both embedding quality and
what the model finally reads.

How a file is split (best fit first, always with a safe fallback):

- **Python** → a real AST parse: each top-level function/class (with its
  decorators and the comment block directly above it) becomes one unit. On a
  syntax error we fall back to the structural splitters below, so a half-written
  file never breaks indexing.
- **Brace languages** (JS/TS, Go, Java, Rust, C/C++, C#, Kotlin, Swift, PHP, and
  HCL/Terraform/JSON) → a brace-depth aware split that only cuts at top level, so
  a whole function / class / resource block stays in one chunk.
- **Markdown** → split by heading sections, never inside a fenced ``` code block.
- **Block config** (YAML, shell, Dockerfile, CI) → blank-line separated blocks.
- **Anything else** → routed by extension, then by a content heuristic (looks
  bracey → brace split), else prose paragraphs.

Common to all: greedily pack consecutive units up to ``max_chars`` (never
splitting a unit unless it alone exceeds the limit), carry a small line-based
overlap across chunk boundaries, merge a tiny trailing fragment back, and
guarantee any non-empty input yields at least one chunk with no content dropped.

``chunk_text`` keeps its original signature for backward compatibility;
``chunk_document`` is the structure-aware entry point used by indexing.
"""

import ast
import re

DEFAULT_CHUNK_MAX_CHARS = 1500
DEFAULT_CHUNK_OVERLAP_CHARS = 200
MIN_CHUNK_CHARS = 200

_HEADING_RE = re.compile(r"^#{1,6}\s")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")

# File types (from the project scanner) that read best as blank-line blocks.
_BLOCK_TYPES = {
    "yaml",
    "shell",
    "docker",
    "gitlab_ci",
    "github_actions",
}

# Scanner types whose syntax is brace/HCL-block structured.
_BRACE_TYPES = {
    "terraform",
    "terragrunt",
    "json",
    "kubernetes",  # often Helm-templated with braces; harmless for plain YAML
    "helm",
}

# Extensions that indicate a brace-structured language when the scanner could not
# classify the file (it reports "unknown" for these source types).
_BRACE_EXTENSIONS = {
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".go", ".java", ".rs", ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx",
    ".cs", ".kt", ".kts", ".scala", ".swift", ".php", ".m", ".mm",
    ".tf", ".hcl", ".json", ".proto", ".dart", ".groovy",
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
    return _pack_units(_split_generic(text), max_chars, overlap)


def chunk_document(
    content: str,
    file_type: str | None = None,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    extension: str | None = None,
) -> list[str]:
    """Structure-aware chunker that adapts splitting to the document type."""
    _validate(max_chars, overlap)
    return _pack_units(_structural_units(content, file_type, extension), max_chars, overlap)


def _structural_units(
    content: str,
    file_type: str | None,
    extension: str | None,
) -> list[str]:
    if file_type == "python":
        units = _split_python_ast(content)
        if units:
            return units
    if file_type == "markdown":
        return _split_markdown(content)
    if file_type in _BRACE_TYPES:
        return _split_brace_aware(content)
    if file_type in _BLOCK_TYPES:
        return _split_blocks(content)

    # The scanner reports "unknown"/None for most source languages — route by the
    # file extension, then fall back to a content heuristic so any file still gets
    # a sensible structural split.
    ext = (extension or "").lower()
    if ext == ".py":
        units = _split_python_ast(content)
        if units:
            return units
    if ext in {".md", ".markdown"}:
        return _split_markdown(content)
    if ext in _BRACE_EXTENSIONS or _looks_bracey(content):
        return _split_brace_aware(content)
    return _split_generic(content)


def _validate(max_chars: int, overlap: int) -> None:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap must be zero or greater")
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")


# --- structure-aware splitters -------------------------------------------------


def _split_python_ast(content: str) -> list[str]:
    """Split Python into units along top-level function/class boundaries, using a
    real AST. Returns [] on a syntax error so the caller can fall back."""
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return []

    lines = content.split("\n")

    def start_line(node: ast.AST) -> int:
        line = node.lineno
        for decorator in getattr(node, "decorator_list", []) or []:
            line = min(line, decorator.lineno)
        # Attach a contiguous comment block sitting directly above the definition.
        i = line
        while i - 1 >= 1 and lines[i - 2].lstrip().startswith("#"):
            i -= 1
        return i

    boundaries = sorted(
        start_line(node)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    if not boundaries:
        return []  # a script with no defs — let block/generic splitting handle it

    units: list[str] = []
    header = "\n".join(lines[: boundaries[0] - 1])
    if header.strip():
        units.append(header)
    for index, start in enumerate(boundaries):
        end = boundaries[index + 1] - 1 if index + 1 < len(boundaries) else len(lines)
        segment = "\n".join(lines[start - 1 : end])
        if segment.strip():
            units.append(segment)
    return units


def _split_brace_aware(content: str) -> list[str]:
    """Split brace-structured code into top-level blocks. Lines are accumulated
    and a boundary is taken only when brace depth returns to zero (the end of a
    function/class/resource block) or at a blank line between top-level items, so
    a whole block is never split across chunks."""
    lines = content.split("\n")
    units: list[str] = []
    current: list[str] = []
    depth = 0
    for line in lines:
        current.append(line)
        depth += line.count("{") + line.count("(") - line.count("}") - line.count(")")
        if depth < 0:
            depth = 0
        stripped = line.strip()
        at_top = depth == 0
        ends_block = stripped.endswith(("}", ")", "};", ");"))
        if at_top and (ends_block or stripped == ""):
            if any(item.strip() for item in current):
                units.append("\n".join(current))
            current = []
    if current and any(item.strip() for item in current):
        units.append("\n".join(current))
    cleaned = [unit for unit in units if unit.strip()]
    return cleaned or _non_empty(content)


def _split_markdown(content: str) -> list[str]:
    """Split markdown into heading sections, never breaking inside a fenced code
    block (a ``#`` inside ``` is not a heading)."""
    lines = content.split("\n")
    sections: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        if (
            not in_fence
            and _HEADING_RE.match(line)
            and any(item.strip() for item in current)
        ):
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


def _looks_bracey(content: str) -> bool:
    """Heuristic: does this unclassified file read like a brace language? True
    when balanced braces appear a few times relative to its size."""
    opens = content.count("{")
    closes = content.count("}")
    if opens == 0 or closes == 0:
        return False
    lines = max(1, content.count("\n") + 1)
    return min(opens, closes) >= 2 and (opens + closes) / lines > 0.02


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
