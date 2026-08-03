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
    # TOML/INI tables, Makefile rules and XML elements are all separated by blank
    # lines in practice; the block splitter keeps each stanza whole.
    "config",
    "makefile",
    "xml_config",
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
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".cxx",
    ".cs",
    ".kt",
    ".kts",
    ".scala",
    ".swift",
    ".php",
    ".m",
    ".mm",
    ".tf",
    ".hcl",
    ".json",
    ".proto",
    ".dart",
    ".groovy",
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token)."""
    return max(1, len(text) // 4)


# --- contextual chunk headers --------------------------------------------------
#
# A retrieved chunk is more useful to both the embedder and the model when it
# carries a one-line note about *where it came from* (which file, which section).
# This is the cheap, deterministic half of "contextual retrieval": no LLM call,
# just provenance derived from the chunk's own structure.

_MD_HEADING_TEXT_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*$")
# Generic "this line begins a definition" keywords shared across languages. Pure
# syntax (not project- or tool-specific), used only to label a chunk's section.
_DEF_KEYWORDS = (
    "def",
    "class",
    "function",
    "func",
    "fn",
    "interface",
    "struct",
    "enum",
    "trait",
    "impl",
    "module",
    "resource",
    "type",
    "package",
)
_DEF_LINE_RE = re.compile(
    r"^\s*(?:export\s+|public\s+|private\s+|protected\s+|async\s+|static\s+|final\s+|abstract\s+)*"
    r"(?:" + "|".join(_DEF_KEYWORDS) + r")\b[\s(\"']*([A-Za-z_][\w.\-]*)"
)
_LABEL_MAX_CHARS = 60


def _truncate_label(text: str) -> str:
    label = " ".join(text.split())
    return label[:_LABEL_MAX_CHARS].rstrip() if len(label) > _LABEL_MAX_CHARS else label


def chunk_section_label(
    content: str,
    file_type: str | None = None,
    extension: str | None = None,
) -> str | None:
    """A short label for where a chunk sits — a markdown heading or a
    function/class/block name — derived deterministically from the chunk's own
    text. Returns ``None`` when nothing structural stands out. Best-effort and
    generic; only used to enrich the chunk header, so it never needs to be exact.
    """
    ext = (extension or "").lower()
    is_markdown = file_type == "markdown" or ext in {".md", ".markdown"}
    for raw in content.split("\n")[:20]:
        line = raw.rstrip()
        if not line.strip():
            continue
        if is_markdown:
            heading = _MD_HEADING_TEXT_RE.match(line)
            if heading:
                return _truncate_label(heading.group(1))
            continue
        definition = _DEF_LINE_RE.match(line)
        if definition:
            return _truncate_label(definition.group(1))
    return None


_CONTEXT_HEADER_PREFIX = "[source: "

# Config files answer "how is X configured?" by *key name*, but the value is often
# a short token that dense and keyword search both miss — e.g. asking about
# "content security policy" when the file only spells it `csp` under a nested
# `security:` key. Listing a chunk's config keys in its header makes BM25 hit by
# key name. Only for structured config; keys go in the header (searchable), not the
# embedded body (which stays the clean content).
_CONFIG_KEY_TYPES = {"json", "yaml"}
# A quoted JSON key (`"csp":`) or a YAML key at line start (`  csp:`). Deliberately
# regex, not a real parse: a chunk is usually a *fragment* of the file, so json/yaml
# loaders would choke. Nested keys are wanted (csp lives under security), so this
# matches keys at any depth.
_JSON_KEY_RE = re.compile(r'"([A-Za-z_][\w.\-]{1,48})"\s*:')
_YAML_KEY_RE = re.compile(r"^[ \t-]*([A-Za-z_][\w.\-]{1,48})\s*:(?:\s|$)", re.MULTILINE)
# TOML/INI: a `[tool.ruff]` table header or a `line-length = 100` assignment. Same
# reasoning as above — "what linting rules are configured" must find pyproject.toml
# by the key name, not by hoping the value happens to embed close to the question.
_TOML_KEY_RE = re.compile(
    r"^\s*(?:\[+([A-Za-z_][\w.\-]{1,48})[^\]]*\]+|([A-Za-z_][\w.\-]{1,48})\s*=)",
    re.MULTILINE,
)
_MAX_CONFIG_KEYS = 24
_MAX_CONFIG_KEYS_CHARS = 200


def config_keys(
    content: str,
    file_type: str | None = None,
    extension: str | None = None,
) -> list[str]:
    """The config keys named in a json/yaml chunk, in first-seen order, deduped and
    capped. Empty for non-config chunks. Deterministic, never raises — used only to
    enrich the searchable header, so approximate is fine."""
    ext = (extension or "").lower()
    is_json = file_type == "json" or ext == ".json"
    is_yaml = file_type == "yaml" or ext in {".yml", ".yaml"}
    is_toml = file_type == "config" or ext in {".toml", ".ini", ".cfg", ".properties"}
    if not (is_json or is_yaml or is_toml):
        return []
    if is_json:
        pattern = _JSON_KEY_RE
    elif is_yaml:
        pattern = _YAML_KEY_RE
    else:
        pattern = _TOML_KEY_RE
    seen: dict[str, None] = {}
    used_chars = 0
    for match in pattern.finditer(content):
        # TOML has two alternatives (table header / assignment); take whichever fired.
        key = next((group for group in match.groups() if group), None)
        if not key or key in seen or key.isdigit():
            continue
        if used_chars + len(key) > _MAX_CONFIG_KEYS_CHARS:
            break
        seen[key] = None
        used_chars += len(key) + 2  # + ", "
        if len(seen) >= _MAX_CONFIG_KEYS:
            break
    return list(seen)


def build_contextual_chunk(
    content: str,
    source_path: str,
    position: int,
    total: int,
    file_type: str | None = None,
    extension: str | None = None,
    section_label: str | None = None,
    origin: str | None = None,
) -> str:
    """Prefix a one-line provenance header to a chunk so the model can ground and
    cite it, and the path becomes keyword-searchable. Deterministic, never raises.

    The header is for storage/display only — embed the *clean* chunk via
    :func:`strip_contextual_header` so the dense vector reflects the real content,
    not boilerplate. Example header: ``[source: api/ask.py › ask_endpoint · part 2/5]``.
    For json/yaml the header also lists the chunk's config keys, so "how is X
    configured?" retrieves by key name even when the value is a short token.
    """
    # An extracted document already knows where the text sat (page 12, sheet rows,
    # heading path); that locator beats anything guessed from the text, and it is
    # what the reader needs in order to check the citation.
    label = section_label or chunk_section_label(content, file_type, extension)
    where = source_path if not label else f"{source_path} › {label}"
    suffix = f" · part {position}/{total}" if total > 1 else ""
    keys = config_keys(content, file_type, extension)
    keys_suffix = f" · keys: {', '.join(keys)}" if keys else ""
    # Where the file itself came from, when the file alone is not enough to place it:
    # a diagram in "Design_files/" means nothing until you know it illustrates the
    # page "Design". Absent for ordinary project files.
    origin_suffix = f" · {origin}" if origin else ""
    return f"{_CONTEXT_HEADER_PREFIX}{where}{suffix}{origin_suffix}{keys_suffix}]\n{content}"


def strip_contextual_header(content: str) -> str:
    """Return the chunk body without a leading provenance header, if present.

    Used at embedding time so the vector reflects the real content; the stored
    chunk keeps its header for grounding, citation and keyword search.
    """
    if not content.startswith(_CONTEXT_HEADER_PREFIX):
        return content
    head, sep, rest = content.partition("\n")
    if sep and head.endswith("]"):
        return rest
    return content


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
    # "source_code" spans two dozen languages, so the extension decides: braces for
    # the C-family and its descendants, paragraphs for Ruby/Python-like syntax. That
    # is exactly what the extension fallback below already does — fall through to it
    # rather than guessing here.

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
        if not in_fence and _HEADING_RE.match(line) and any(item.strip() for item in current):
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


# When a single line is too long to fit a chunk (minified code, a huge string
# literal, a data blob), prefer to break just before one of these separators so
# a chunk ends at a natural token boundary instead of mid-identifier — better
# embeddings than a blind character cut.
_SOFT_BREAK_CHARS = frozenset(" \t,;)]}")


def _soft_boundary(text: str, start: int, hard_end: int, max_chars: int) -> int:
    """Best break point at or before ``hard_end`` for a single long line.

    Searches back a bounded window for a separator and returns the index just
    after it (keeping the separator with the current chunk). Falls back to the
    hard character cut when no separator is near, so progress is guaranteed.
    """
    lookback = max(1, max_chars // 5)
    floor = max(start + 1, hard_end - lookback)
    for index in range(hard_end - 1, floor - 1, -1):
        if text[index] in _SOFT_BREAK_CHARS:
            return index + 1
    return hard_end


def _hard_split(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split a single oversized unit: prefer line boundaries, then soft
    separators within a line, then a blind character cut as a last resort."""
    lines = text.split("\n")
    if len(lines) > 1:
        return _pack_units(lines, max_chars, overlap)

    pieces: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        hard_end = min(start + max_chars, length)
        end = hard_end if hard_end == length else _soft_boundary(text, start, hard_end, max_chars)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= length:
            break
        # Advance with overlap, but always make forward progress.
        next_start = end - overlap if overlap > 0 else end
        start = next_start if next_start > start else end
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
