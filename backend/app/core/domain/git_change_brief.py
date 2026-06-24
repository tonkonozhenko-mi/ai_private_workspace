"""A human-readable "what the team did since you last looked" brief, built from
git history — not the entity graph.

The graph diff answers "what structures changed"; this answers the question a
person on a team actually asks: how many commits landed, who made them, and which
areas of the codebase moved. The git data is collected by an adapter; everything
here is pure and deterministic so it is easy to test and reads grammatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GitChangeBrief:
    # Whether we had a previous baseline commit to compare against. On the very
    # first check there is nothing to diff, so the brief is informational only.
    comparable: bool
    head: str | None
    commit_count: int
    authors: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)


def top_changed_areas(changed_paths: list[str], limit: int = 4) -> list[tuple[str, int]]:
    """Group changed files by their top-level folder and count them, most-changed
    first. Files at the repo root are grouped under "(root)"."""
    counts: dict[str, int] = {}
    for path in changed_paths:
        clean = path.strip().strip("/")
        if not clean:
            continue
        area = clean.split("/", 1)[0] if "/" in clean else "(root)"
        counts[area] = counts.get(area, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:limit]


def _join_authors(authors: list[str], limit: int = 3) -> str:
    names = [a for a in authors if a]
    if not names:
        return "someone"
    if len(names) <= limit:
        if len(names) == 1:
            return names[0]
        return ", ".join(names[:-1]) + " and " + names[-1]
    shown = ", ".join(names[:limit])
    return f"{shown} and {len(names) - limit} other{'s' if len(names) - limit != 1 else ''}"


def format_git_brief(brief: GitChangeBrief) -> list[str]:
    """Human lines describing the work since the last check. Empty list when there
    is nothing meaningful to say (no baseline, or no new commits)."""
    if not brief.comparable:
        return []
    if brief.commit_count <= 0:
        return ["No new commits since your last check."]

    commits = (
        f"{brief.commit_count} commit{'s' if brief.commit_count != 1 else ''}"
    )
    lines = [f"{commits} by {_join_authors(brief.authors)} since your last check."]

    areas = top_changed_areas(brief.changed_paths)
    if areas:
        rendered = ", ".join(
            f"{area} ({count} file{'s' if count != 1 else ''})" for area, count in areas
        )
        lines.append(f"Most changes in {rendered}.")
    return lines
