"""A folder of documentation, read as a body of knowledge.

Point the app at an exported wiki and, until now, it answered with a list of things
it did not find: no infrastructure, no environments, no pipelines. Every line true,
and the whole screen a lie — the project is not broken, it is simply not a code
repository. Absence of facts is not a fact.

Documentation has facts of its own, and they are as deterministic as a Terraform
file. They are just different ones:

* **Pages and areas.** Titles carry structure — "[ADR-08] Sequence generation",
  "[Capability] Ingestion layer" — and a wiki's own naming convention is the closest
  thing it has to a schema. Whatever bracket or prefix a team uses, the shape is the
  same: a tag, then a name.
* **Links.** Who points at whom. A page nobody links to is a page nobody finds.
* **Decisions.** ADRs are not ordinary pages: they are the record of what was chosen
  and when, and they are what people come looking for.
* **Freshness.** The signature failure of a wiki is not a missing page, it is a page
  that is confidently out of date — especially one everybody else still links to.
* **Attachments.** Diagrams and spreadsheets, and which page they illustrate.

Nothing here reads a mind or guesses intent. It reads names, links and dates, and it
says only what those support: "this page has not changed in 14 months and 6 pages
point at it" is a fact to check, not a verdict on anyone's work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from html import unescape
from urllib.parse import unquote

from app.core.domain.companion_assets import document_title, owning_document

# A page whose title starts with a bracketed tag — "[ADR-08]", "[Capability]",
# "[DMD-1]" — belongs to the area that tag names. Teams differ in what they put in
# the brackets; the convention itself is near-universal in exported wikis.
_AREA_TAG_RE = re.compile(r"^\s*[\[(<]\s*([^\]\)>]{1,40})\s*[\])>]")
# The same idea without brackets: "ADR-08 - Sequence generation", "RFC 12: Naming".
_AREA_PREFIX_RE = re.compile(r"^\s*([A-Za-z]{2,12})[-_ ]?\d{1,4}\b")
# An area tag that names a decision record, whatever the local acronym.
_DECISION_WORDS = ("adr", "decision", "rfc", "design record")
# Links inside a saved page. Anchors, mail and external URLs are not navigation
# between our own pages, so they are ignored.
_HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#>]+)["']""", re.IGNORECASE)
# Markdown's own link syntax, for wikis exported as .md.
_MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")

# How old a page must be before "nobody has touched this in a long time" is worth
# saying at all. A year is deliberately generous: documentation is allowed to be
# stable, and crying stale at three months would train people to ignore us.
STALE_AFTER = timedelta(days=365)
# …and how many other pages must still point at it before that staleness is a *risk*
# rather than a triviality. One forgotten page harms nobody; a forgotten page that
# six others treat as the source of truth is how a team ends up acting on last year's
# decision.
STALE_INBOUND_LINKS = 3


@dataclass(frozen=True)
class KnowledgeDocument:
    """One page, and what the folder itself says about it."""

    path: str
    title: str
    area: str | None = None
    modified_at: datetime | None = None
    is_decision: bool = False
    # Paths this page links to, and files that live in its companion folder.
    links_to: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    diagrams: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnowledgeBase:
    documents: list[KnowledgeDocument] = field(default_factory=list)
    # Area → number of pages, biggest first. The wiki's own table of contents.
    areas: dict[str, int] = field(default_factory=dict)
    # path → how many other pages link to it.
    inbound_links: dict[str, int] = field(default_factory=dict)

    @property
    def decisions(self) -> list[KnowledgeDocument]:
        return [document for document in self.documents if document.is_decision]

    @property
    def orphans(self) -> list[KnowledgeDocument]:
        """Pages nothing links to. Not a defect — an entry point is an orphan by
        definition — but the place unread pages hide."""
        return [
            document
            for document in self.documents
            if not self.inbound_links.get(document.path)
            and not _looks_like_an_entry_point(document)
        ]

    def stale_but_relied_on(self, now: datetime | None = None) -> list[KnowledgeDocument]:
        """Pages that have not changed in a long time and that other pages still
        point at. The most expensive kind of wrong: confidently out of date."""
        moment = now or datetime.now(timezone.utc)
        out = []
        for document in self.documents:
            if document.modified_at is None:
                continue
            age = moment - document.modified_at
            inbound = self.inbound_links.get(document.path, 0)
            if age >= STALE_AFTER and inbound >= STALE_INBOUND_LINKS:
                out.append(document)
        return sorted(out, key=lambda d: self.inbound_links.get(d.path, 0), reverse=True)


def _looks_like_an_entry_point(document: KnowledgeDocument) -> bool:
    name = document.path.rsplit("/", 1)[-1].lower()
    return name.startswith(("index.", "home.", "readme.", "toc."))


def area_of(title: str) -> str | None:
    """The area a page's title announces, or None when it announces none.

    "[ADR-08] Sequence generation" → "ADR-08"; "RFC 12: Naming" → "RFC". The tag is
    returned as written — we are reporting the team's own convention, not inventing a
    taxonomy for them.
    """
    bracketed = _AREA_TAG_RE.match(title)
    if bracketed:
        return " ".join(bracketed.group(1).split())
    prefixed = _AREA_PREFIX_RE.match(title)
    if prefixed:
        return prefixed.group(1).upper()
    return None


def area_family(area: str | None) -> str | None:
    """ "ADR-08" and "ADR-11" are the same family: "ADR". Used to count areas, so a
    wiki with 40 numbered ADRs shows one area of 40, not 40 areas of one."""
    if not area:
        return None
    match = re.match(r"^([A-Za-z][A-Za-z .]*?)[-_ ]?\d+$", area.strip())
    return (match.group(1) if match else area).strip().upper()


def is_decision(title: str, path: str) -> bool:
    haystack = f"{area_family(area_of(title)) or ''} {title} {path}".lower()
    return any(word in haystack for word in _DECISION_WORDS)


@dataclass(frozen=True)
class PageSource:
    """What the scan can hand us for one page, before anything is inferred."""

    path: str
    text: str = ""
    modified_at: datetime | None = None


# Titles a page can claim that tell the reader nothing. A wiki's own boilerplate
# ("General Information", "Untitled") ends up in <title> or the first heading of
# dozens of exported pages; taking it at face value produced a Documents tab that
# was a column of the same two words, and decisions nobody could tell apart.
_EMPTY_TITLES = {
    "general information",
    "untitled",
    "untitled page",
    "confluence",
    "page",
    "home",
    "wiki",
}


# A title is a line, not a page. Some exported pages have an <h1> whose closing tag is
# nowhere near it, so a greedy-enough read swallowed the entire document and offered it
# as the page's "name" — screenfuls of flattened prose in a list of titles. Anything
# this long is not a title, whatever the markup claims.
_MAX_TITLE_CHARS = 120


def title_of(page: PageSource) -> str:
    """The page's own title if it states a useful one, else the file name.

    A saved page states its title in <title> and again in the first heading. Both beat
    the underscored file name — but only when they say something. When the page's own
    title is boilerplate, absurdly long, or shared by dozens of pages, the file name
    (which the author did choose) is the more honest answer.
    """
    for pattern in (r"<title[^>]*>(.*?)</title>", r"<h1[^>]*>(.*?)</h1>", r"^#\s+(.+)$"):
        match = re.search(pattern, page.text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if not match:
            continue
        title = unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
        title = " ".join(title.split())
        # Exports prefix the space name: "Data Platform : Ingestion layer".
        title = title.split(" : ")[-1].strip()
        if not title or len(title) > _MAX_TITLE_CHARS:
            continue
        if title.lower() not in _EMPTY_TITLES:
            return title
    return document_title(page.path)


def build_knowledge_base(
    pages: list[PageSource],
    all_paths: list[str] | None = None,
) -> KnowledgeBase:
    """The facts a folder of documentation carries about itself.

    ``all_paths`` is every file the scan found, which is what lets an attachment be
    tied to the page it illustrates. Everything else is read off the pages: their
    titles, the links between them, and when they last changed.
    """
    known = set(all_paths or [path.path for path in pages])
    by_path = {page.path: page for page in pages}

    # Attachments first: each non-page file that lives in a page's companion folder
    # belongs to that page. This is the same rule the index uses when it cites them.
    attachments: dict[str, list[str]] = {}
    diagrams: dict[str, list[str]] = {}
    for path in sorted(known):
        owner = owning_document(path, known)
        if owner is None or owner not in by_path:
            continue
        attachments.setdefault(owner, []).append(path)
        if path.lower().endswith((".drawio", ".drawio.xml")):
            diagrams.setdefault(owner, []).append(path)

    # A title several pages share is not a title, it is the export's boilerplate. The
    # file name is then the closest thing to what the author actually called the page.
    claimed: dict[str, int] = {}
    for page in pages:
        claimed[title_of(page)] = claimed.get(title_of(page), 0) + 1

    documents: list[KnowledgeDocument] = []
    inbound: dict[str, int] = {}
    for page in pages:
        title = title_of(page)
        if claimed.get(title, 0) > 1:
            title = document_title(page.path)
        area = area_of(title)
        targets = _resolve_links(page, links_from(page.text), known)
        for target in targets:
            if target != page.path:
                inbound[target] = inbound.get(target, 0) + 1
        documents.append(
            KnowledgeDocument(
                path=page.path,
                title=title,
                area=area,
                modified_at=page.modified_at,
                is_decision=is_decision(title, page.path),
                links_to=targets,
                attachments=attachments.get(page.path, []),
                diagrams=diagrams.get(page.path, []),
            )
        )

    areas: dict[str, int] = {}
    for document in documents:
        family = area_family(document.area)
        if family:
            areas[family] = areas.get(family, 0) + 1

    return KnowledgeBase(
        documents=sorted(documents, key=lambda d: d.path),
        areas=dict(sorted(areas.items(), key=lambda item: (-item[1], item[0]))),
        inbound_links=inbound,
    )


def _resolve_links(page: PageSource, hrefs: list[str], known: set[str]) -> list[str]:
    """Turn the hrefs on a page into paths of pages we actually have.

    A link to a page that was not exported is not a link we can follow, and counting
    it would inflate every number downstream. Relative links are resolved against the
    linking page's own folder, the way a browser would.
    """
    base = page.path.rsplit("/", 1)[0] if "/" in page.path else ""
    resolved: list[str] = []
    for href in hrefs:
        candidate = unquote(href)
        for target in (
            f"{base}/{candidate}" if base else candidate,
            candidate,
        ):
            normalised = PurePosixPath(target).as_posix()
            if normalised in known and normalised not in resolved:
                resolved.append(normalised)
                break
    return resolved


def links_from(text: str, file_type: str | None = None) -> list[str]:
    """Links to other local pages — anchors, mailto: and http(s) are not navigation
    inside this folder, so they are dropped."""
    raw = _HREF_RE.findall(text) + _MD_LINK_RE.findall(text)
    out: list[str] = []
    for href in raw:
        href = href.strip()
        if not href or "://" in href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        out.append(href)
    return out
