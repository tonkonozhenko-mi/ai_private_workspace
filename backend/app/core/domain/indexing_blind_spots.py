"""What the scan walked past without recognising, counted and named.

An Azure repository was scanned, indexed, and answered questions — and every
`.bicep` and `.ps1` in it was invisible, because the extension dictionary had
never heard of them. The file was found, counted in the totals, classified as
"unknown", and then silently dropped at the index step. Nothing anywhere said so.
The person saw a project that had been read, and asked it questions about
infrastructure it had never seen.

Adding the extensions fixes those two. It does not fix the shape of the problem:
there will always be a next extension, and the index will always be the last to
mention it. So the count is surfaced instead of the excuse —

    "14 files I can't read yet: .bicep ×12, .ps1 ×2"

— which is the same honesty the rest of the app owes: not knowing is not the same
as knowing there is nothing.

Two things are deliberately *not* in this count.

*Files the person excluded themselves.* Their include/exclude rules are answered
before this code ever runs — an excluded file is not in the scan at all. That is
as it should be: "I didn't ask for it" is not "I can't read it", and printing
someone's own decision back to them as a limitation would be nonsense.

*Files with no extension at all.* LICENSE, Procfile, a bare Jenkinsfile — some of
those are real blind spots, but this line's whole job is to name extensions, and
a total that includes what it cannot itemise ("20 files: .bicep ×12, .ps1 ×2")
adds up to less than it claims. A number that does not add up is worse than a
smaller number that does.

Pure: counts and extensions, never paths. The line appears on a Home screen and
in a prompt, and neither is a place to leak a directory listing.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.source_files import (
    is_build_output,
    is_lockfile,
    is_os_clutter,
    is_secret_env_file,
)

# "unknown" is what the classifier returns when nothing claimed the file. It is
# also the one detected type, other than "image", that the index refuses — and an
# image is a *known* limit ("we cannot read a picture"), not a blind spot, so it
# is not counted here. A test guards that this stays true of the indexable set.
UNRECOGNISED_TYPE = "unknown"

# How many extensions the sentence names before it stops. Four is enough to
# recognise what kind of work is missing; past that the line stops being a line.
_NAMED_EXTENSIONS = 4


@dataclass(frozen=True)
class UnreadFiles:
    """Files the scan found and the index could not take, by extension."""

    total: int
    by_extension: tuple[tuple[str, int], ...]

    @property
    def is_empty(self) -> bool:
        return self.total == 0

    def summary(self) -> dict[str, int]:
        """The shape stored beside the scan: ``{".bicep": 12, ".ps1": 3}``."""
        return dict(self.by_extension)


EMPTY = UnreadFiles(total=0, by_extension=())


def _is_deliberately_refused(path: str) -> bool:
    """True for a file we classify as "unknown" *on purpose*.

    A lockfile, a minified bundle and a real ``.env`` are all left unknown so they
    never reach the index — and each of those is a decision, not a gap. Calling
    them "files I can't read" would turn our own judgement into an apology.
    """
    name = path.rsplit("/", 1)[-1]
    return (
        is_lockfile(name)
        or is_secret_env_file(name)
        or is_os_clutter(name)
        or is_build_output(path)
    )


def unread_files(files) -> UnreadFiles:
    """Summarise, by extension, what the scan could not recognise.

    ``files`` is any iterable of scanned files with ``path``, ``extension`` and
    ``detected_type``. Files the person excluded are absent by construction —
    they were filtered before the scan result was built.
    """
    counts: dict[str, int] = {}
    for project_file in files or ():
        if project_file.detected_type != UNRECOGNISED_TYPE:
            continue
        extension = (project_file.extension or "").lower()
        if not extension:
            continue
        if _is_deliberately_refused(project_file.path):
            continue
        counts[extension] = counts.get(extension, 0) + 1

    if not counts:
        return EMPTY
    # Most-common first; ties alphabetical, so the same project always produces
    # the same sentence.
    ordered = tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return UnreadFiles(total=sum(counts.values()), by_extension=ordered)


def unread_files_in_scan(scan) -> UnreadFiles:
    """Everything a scan could not read: what it took in and could not name, plus
    what the default rules cut before it could look.

    Two sources, one number, because to the person they are one fact. The split
    is ours: a file under `src/` reached the classifier and came back "unknown",
    while the same file under `infra/` never got that far — but both are files
    the app cannot answer questions from, and reporting only the first is how
    `infra/appservice.bicep` was invisible twice over.

    ``scan`` may be None, or predate the field; both mean nothing to report.
    """
    if scan is None:
        return EMPTY
    return unread_files([*scan.files, *getattr(scan, "unseen_files", ())])


def _extension_phrases(unread: UnreadFiles) -> list[str]:
    shown = unread.by_extension[:_NAMED_EXTENSIONS]
    named = [f"{extension} ×{count}" for extension, count in shown]
    remaining = len(unread.by_extension) - _NAMED_EXTENSIONS
    if remaining > 0:
        named.append(f"and {remaining} more")
    return named


def unread_files_note(unread: UnreadFiles) -> str:
    """The line shown on Home, or "" when there is nothing to say.

    Empty means empty: no "0 files skipped", no reassuring green tick. A screen
    that stays quiet when all is well is how the person learns to read the line
    when it appears.
    """
    if unread.is_empty:
        return ""
    files = "file" if unread.total == 1 else "files"
    return f"{unread.total} {files} I can't read yet: {', '.join(_extension_phrases(unread))}"


def unread_files_prompt_note(unread: UnreadFiles) -> str:
    """The sentence added to the Ask prompt, or "" when nothing was skipped.

    The model cannot notice an absence — a missing file leaves no gap in what it
    is handed. So the absence is stated, along with what to do about it, which is
    to say so rather than to answer confidently from what happens to be there.
    """
    if unread.is_empty:
        return ""
    extensions = ", ".join(extension for extension, _ in unread.by_extension[:_NAMED_EXTENSIONS])
    files = "file" if unread.total == 1 else "files"
    return (
        f"Note: {unread.total} {files} with extensions {extensions} were not indexed "
        f"and are invisible to you; say so if the question may depend on them."
    )
