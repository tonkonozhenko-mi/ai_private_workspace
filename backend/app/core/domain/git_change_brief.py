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
    # Commit subject lines (newest first), used as the raw material for an
    # optional one-tap LLM summary. Capped by the adapter.
    commit_subjects: list[str] = field(default_factory=list)


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

    commits = f"{brief.commit_count} commit{'s' if brief.commit_count != 1 else ''}"
    lines = [f"{commits} by {_join_authors(brief.authors)} since your last check."]

    areas = top_changed_areas(brief.changed_paths)
    if areas:
        rendered = ", ".join(
            f"{area} ({count} file{'s' if count != 1 else ''})" for area, count in areas
        )
        lines.append(f"Most changes in {rendered}.")
    return lines


# Token budgeting for the optional LLM summary. We measure in characters at a
# rough 4-chars-per-token ratio so the prompt always fits the answer window,
# regardless of how many commits landed.
_CHARS_PER_TOKEN = 4
_RESPONSE_RESERVE_TOKENS = 512
_PROMPT_OVERHEAD_TOKENS = 384


def build_change_summary_prompt(
    brief: GitChangeBrief, max_context_tokens: int = 8192
) -> str | None:
    """A prompt asking the local model to summarise, in 2-3 plain sentences, what
    the commits since the last check accomplished — grounded only in their subject
    lines. Returns ``None`` when there is nothing to summarise (no baseline or no
    commits), so the caller can skip the model call entirely.

    The commit list is trimmed to fit ``max_context_tokens`` so a busy day with
    hundreds of commits never overflows the answer window.
    """
    if not brief.comparable or brief.commit_count <= 0:
        return None
    subjects = [s.strip() for s in brief.commit_subjects if s.strip()]
    if not subjects:
        return None

    content_budget = max(
        200,
        (max_context_tokens - _RESPONSE_RESERVE_TOKENS - _PROMPT_OVERHEAD_TOKENS)
        * _CHARS_PER_TOKEN,
    )

    kept: list[str] = []
    used = 0
    for subject in subjects:
        line = f"- {subject}\n"
        if used + len(line) > content_budget and kept:
            break
        kept.append(subject)
        used += len(line)
    omitted = len(subjects) - len(kept)

    authors = _join_authors(brief.authors)
    commit_word = "commit" if brief.commit_count == 1 else "commits"
    header_lines = [
        "You are helping a developer who is returning to a shared project catch up.",
        "Summarise what changed since they last looked, in 2-3 short plain-language",
        "sentences. Use only the commit messages below — do not invent details, file",
        "names, or numbers that are not present. Group related commits and describe",
        "what the work accomplished, not a commit-by-commit list.",
        "",
        f"{brief.commit_count} {commit_word} by {authors}:",
    ]
    body = "\n".join(f"- {s}" for s in kept)
    if omitted > 0:
        body += f"\n- (+{omitted} more commits not shown)"

    areas = top_changed_areas(brief.changed_paths)
    area_line = ""
    if areas:
        rendered = ", ".join(
            f"{area} ({count} file{'s' if count != 1 else ''})" for area, count in areas
        )
        area_line = f"\nMost-changed areas: {rendered}."

    return "\n".join(header_lines) + "\n" + body + area_line + "\n\nSummary:"
