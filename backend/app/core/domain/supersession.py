"""Following the pointer a superseded page leaves behind.

A decision that has been overruled names its replacement in the same breath:
"**Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md)**".
That is not a hint, it is an address — and until now the app read the first half
of the sentence (this page is dead) and threw away the second (here is the live
one). Telling a model that a page is superseded without giving it the successor
turns out to be worse than saying nothing: told the decision had been replaced
and not shown by what, it invented the replacement's contents (observed
2026-07-15 — "stored in S3", from a page it had never seen).

So: read the address, fetch what it points at, put it in front of the model. One
hop, and only where the page itself points. The successor's own status line will
fire on the next question if it, too, has been replaced — following a chain is
not this module's business.

Everything here is pure text: the parsing, and the matching of a pointer against
paths that exist. The fetching lives in the use case.
"""

from __future__ import annotations

import re

# "Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md)" — a
# Markdown link. Only the parenthesised half is matched: the label before it is a
# page title that itself contains brackets ("[ADR-08] Report storage v2"), and any
# attempt to parse the label is a bracket-counting exercise with nothing to gain.
# What is inside the parentheses is a path someone can open, and that is the point.
_MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
# "Superseded by [[Report storage v2]]" — a wiki link: no path, a title instead.
_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
# "Superseded by ADR-08." — no link at all; whatever follows the phrase is the
# best address we have.
_AFTER_MARKER_RE = re.compile(
    r"(?:superseded|replaced|supplanted)\s+by[:\s]+(.+)",
    re.IGNORECASE,
)
# Markdown emphasis and the punctuation a sentence ends with — noise around a
# title. Brackets are NOT trimmed from a path: "[ADR-08]_Report_storage_v2.md" is
# a filename whose brackets a wiki exporter put there on purpose, and stripping
# them turns a real address into one that resolves to nothing.
_TRIM_TITLE = " \t*_`.,;:!?()[]<>\"'"
_TRIM_PATH = " \t*`\"'"
# A pointer longer than this is a paragraph, not an address.
_MAX_TARGET_CHARS = 120


def supersession_target(status_line: str) -> str | None:
    """The successor a status line points at: a path if it gives one, else a title.

    Returns ``None`` when the line names nothing followable — a page that says
    only "Deprecated." has told us it is dead and nothing more, which is a fact
    worth stating to the model but not an address worth chasing.
    """
    if not status_line:
        return None
    link = _MARKDOWN_LINK_RE.search(status_line)
    if link:
        target = link.group(1).strip(_TRIM_PATH)
        if target and len(target) <= _MAX_TARGET_CHARS:
            return target
    wiki = _WIKI_LINK_RE.search(status_line)
    if wiki:
        target = wiki.group(1).strip(_TRIM_TITLE)
        if target and len(target) <= _MAX_TARGET_CHARS:
            return target
    after = _AFTER_MARKER_RE.search(status_line)
    if after:
        # Take the first clause: "superseded by ADR-08, see the migration notes"
        # points at ADR-08; the rest is commentary.
        target = after.group(1).split(",")[0].strip(_TRIM_TITLE)
        if target and len(target) <= _MAX_TARGET_CHARS:
            return target
    return None


def _slug(text: str) -> str:
    """A comparison key that survives the trip from a title to a filename.

    "[ADR-08] Report storage v2" and "[ADR-08]_Report_storage_v2.md" are the same
    page written twice — once by a person, once by whatever exported the wiki.
    Everything that differs between the two (spaces, underscores, dashes, the
    extension, case) is exactly what this drops.
    """
    without_extension = re.sub(r"\.[A-Za-z0-9]{1,6}$", "", text.strip())
    return re.sub(r"[^a-z0-9]+", "", without_extension.lower())


def resolve_successor_path(target: str, candidate_paths: list[str]) -> str | None:
    """The indexed file a pointer refers to, or ``None`` if it is not indexed.

    Deterministic on purpose — no embeddings, no model. A pointer is an address,
    and looking up an address is a lookup, not a guess. Matched three ways, in
    order of confidence: the path itself, the path's tail, and the page's name
    with the punctuation normalised away.

    ``None`` is a real answer: the successor may live in another project, or not
    have been written yet. The caller says so rather than inventing it.
    """
    if not target or not candidate_paths:
        return None
    wanted = target.strip().lstrip("./")
    if not wanted:
        return None
    for path in candidate_paths:
        if path == wanted:
            return path
    # The pointer is usually relative to the page that carries it ("[ADR-08]_x.md"
    # from inside wiki/), so the tail is what matches.
    for path in candidate_paths:
        if path.endswith(f"/{wanted}") or path == wanted:
            return path
    wanted_slug = _slug(wanted)
    if not wanted_slug:
        return None
    for path in candidate_paths:
        if _slug(path.split("/")[-1]) == wanted_slug:
            return path
    return None
