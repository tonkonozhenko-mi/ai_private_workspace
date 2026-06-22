"""Deterministic group handbook — a plain-language briefing for a whole group.

Built only from the aggregated overview (which is itself built from each member's
persisted facts and git history). No LLM, no guessing: the same inputs always
produce the same handbook. It is stored as the group's singleton handbook memory
so Ask can lean on it.
"""

from app.core.domain.group_overview import GroupOverview


def build_group_handbook(overview: GroupOverview) -> str:
    lines: list[str] = [f"# {overview.name} — group handbook", ""]
    lines.append(
        f"A group of {overview.member_count} "
        f"{'repository' if overview.member_count == 1 else 'repositories'} treated as one project."
    )

    totals = overview.totals
    rollup = []
    if totals.get("services"):
        rollup.append(f"{totals['services']} service(s)")
    if overview.environments:
        rollup.append(f"{len(overview.environments)} environment(s)")
    if totals.get("commits_last_7_days"):
        rollup.append(f"{totals['commits_last_7_days']} commit(s) this week")
    if rollup:
        lines += ["", "Across the group: " + ", ".join(rollup) + "."]

    if overview.members:
        lines += ["", "## Repositories"]
        for member in overview.members:
            detail = member.description if member.built else "not analyzed yet"
            lines.append(f"- **{member.name}** — {detail}")

    if overview.environments:
        lines += ["", "## Environments", ", ".join(overview.environments)]

    if overview.technologies:
        lines += ["", "## Technologies", ", ".join(overview.technologies)]

    if overview.risks:
        lines += ["", "## Risks worth a look"]
        for risk in overview.risks:
            lines.append(f"- [{risk.severity}] {risk.title} ({risk.workspace_name})")

    lines += [
        "",
        "## Where to start",
        "Pick the repository most relevant to your task — each has its own map, "
        "history and search index. Ask the group to find where something lives "
        "across all of them at once.",
    ]
    return "\n".join(lines).strip() + "\n"
