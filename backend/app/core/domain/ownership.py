"""Who knows this code — and what happens when they leave.

The manager's lens had no facts of its own: it reordered pipelines and environments
like everyone else's. But the manager's real question is not "how does this deploy",
it is "where are we exposed". Git already knows the answer, and has all along.

A file whose entire history was written by one person is a file only that person
understands. That is the bus factor, and it is a fact — not an accusation. Someone
being the sole author of a file is normal and often good; a *busy* file with a sole
author is a risk worth naming out loud.

Pure: no I/O, no state. The git adapter supplies the history; this decides what it
means.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# A file has to matter before its ownership matters: three commits is the point
# where a file is being actively worked on rather than written once and forgotten.
_MIN_COMMITS_TO_COUNT = 3
# One author writing everything is only a warning sign above this share.
_SOLE_AUTHOR_SHARE = 0.9


@dataclass(frozen=True)
class FileOwnership:
    path: str
    commits: int
    top_author: str
    top_author_share: float
    authors_count: int

    @property
    def is_single_owner(self) -> bool:
        return self.authors_count == 1 or self.top_author_share >= _SOLE_AUTHOR_SHARE


@dataclass(frozen=True)
class OwnershipFacts:
    files: list[FileOwnership] = field(default_factory=list)
    # People who alone hold most of what they touch, with how many busy files each.
    key_people: list[tuple[str, int]] = field(default_factory=list)

    @property
    def single_owner_files(self) -> list[FileOwnership]:
        return [f for f in self.files if f.is_single_owner]

    @property
    def bus_factor(self) -> int:
        """How many people would have to leave before a busy part of the codebase is
        left with nobody who has ever touched it. Not a score out of ten: the plain
        count of people who are the sole author of at least one busy file."""
        return len({f.top_author for f in self.single_owner_files})


def build_ownership_facts(
    activity: list[tuple[str, int, list[tuple[str, int]]]],
    limit: int = 12,
) -> OwnershipFacts:
    """``activity`` is [(path, total_commits, [(author, commits), …])] from git.

    Files below the activity floor are dropped — the question is who owns the code
    that is *alive*, and a file touched once in 2019 tells the manager nothing.
    """
    files: list[FileOwnership] = []
    for path, commits, authors in activity:
        if commits < _MIN_COMMITS_TO_COUNT or not authors:
            continue
        top_author, top_commits = max(authors, key=lambda item: item[1])
        total_by_authors = sum(count for _, count in authors) or 1
        files.append(
            FileOwnership(
                path=path,
                commits=commits,
                top_author=top_author,
                top_author_share=top_commits / total_by_authors,
                authors_count=len(authors),
            )
        )

    files.sort(key=lambda f: (-f.commits, f.path))

    counts: dict[str, int] = {}
    for file in files:
        if file.is_single_owner:
            counts[file.top_author] = counts.get(file.top_author, 0) + 1
    key_people = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    return OwnershipFacts(files=files[:limit], key_people=key_people[:5])
