"""When a group's handbook was built, measured against what it was built from.

A handbook is a summary of every member repository, and a summary is only as
current as the thing it summarised. Re-index one member and the handbook is
quietly behind — still useful (an old summary beats no summary), but no longer
describing what the app now knows.

Rather than watch for changes, the handbook records what it read: each member's
index timestamp at the moment it was written. Whether it has fallen behind is
then arithmetic on two sets of marks — no watcher, no log, no model. The record
lives in the handbook's own provenance field, because it is a fact about the
handbook and nothing else has any business holding it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

_PREFIX = "Built from indexes: "
_NEVER = "never"


def format_index_snapshot(marks: Mapping[str, str | None]) -> str:
    """The provenance line stored on the handbook: who it read, and how fresh."""
    if not marks:
        return ""
    parts = [f"{workspace_id}@{mark or _NEVER}" for workspace_id, mark in sorted(marks.items())]
    return _PREFIX + ", ".join(parts)


def has_index_snapshot(grounding: str | None) -> bool:
    """Whether this handbook recorded what it read at all.

    A handbook written before it kept provenance has no snapshot, and no snapshot
    is not evidence of being behind — it is evidence of not knowing. We say
    nothing rather than nag on a guess; the next rebuild records one.
    """
    return bool(grounding) and grounding.startswith(_PREFIX)


def parse_index_snapshot(grounding: str | None) -> dict[str, str]:
    """The marks back out of the line. Members with no index at build time are
    absent, which is the same as not having been read."""
    if not grounding or not grounding.startswith(_PREFIX):
        return {}
    snapshot: dict[str, str] = {}
    for part in grounding[len(_PREFIX) :].split(","):
        workspace_id, separator, mark = part.strip().rpartition("@")
        if not separator or not workspace_id or mark == _NEVER:
            continue
        snapshot[workspace_id] = mark
    return snapshot


def handbook_lag(
    snapshot: Mapping[str, str],
    current: Mapping[str, str | None],
) -> tuple[str, ...]:
    """Members whose index has moved on since the handbook read it.

    A member that has never been indexed cannot have moved on. A member that has
    been indexed and is absent from the snapshot joined the group afterwards —
    the handbook has never heard of it, which is the same lag by another route.
    """
    behind = [
        workspace_id
        for workspace_id, mark in current.items()
        if mark is not None and _is_newer(mark, snapshot.get(workspace_id))
    ]
    return tuple(sorted(behind))


def _is_newer(mark: str, than: str | None) -> bool:
    if than is None:
        return True
    left, right = _instant(mark), _instant(than)
    if left is None or right is None:
        # Unparseable timestamps: compare as written rather than guess. Both were
        # produced by the same writer, so this holds for every mark we make.
        return mark > than
    return left > right


def _instant(mark: str) -> datetime | None:
    try:
        return datetime.fromisoformat(mark)
    except ValueError:
        return None
