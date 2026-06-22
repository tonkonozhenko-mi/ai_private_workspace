"""Project group domain.

A *group* lets several repositories be treated as one project. It owns an ordered
list of member workspace ids; every heavier surface (Ask, Home, Intelligence)
aggregates over those members. The group itself holds no project files — it is a
thin, deterministic container, which keeps each member independently scannable
and rebuildable.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ProjectGroup:
    id: str
    name: str
    workspace_ids: tuple[str, ...] = ()
    created_at: str = ""

    @property
    def member_count(self) -> int:
        return len(self.workspace_ids)


def rename_group(group: ProjectGroup, name: str) -> ProjectGroup:
    """Return a copy with a new name; blank names are ignored."""
    cleaned = name.strip()
    if not cleaned:
        return group
    return replace(group, name=cleaned)


def add_member(group: ProjectGroup, workspace_id: str) -> ProjectGroup:
    """Append a member, keeping order and ignoring duplicates."""
    if not workspace_id or workspace_id in group.workspace_ids:
        return group
    return replace(group, workspace_ids=(*group.workspace_ids, workspace_id))


def remove_member(group: ProjectGroup, workspace_id: str) -> ProjectGroup:
    """Drop a member if present; a no-op otherwise."""
    if workspace_id not in group.workspace_ids:
        return group
    return replace(
        group,
        workspace_ids=tuple(w for w in group.workspace_ids if w != workspace_id),
    )


def set_members(group: ProjectGroup, workspace_ids: list[str]) -> ProjectGroup:
    """Replace the member list, preserving order and de-duplicating."""
    seen: list[str] = []
    for workspace_id in workspace_ids:
        if workspace_id and workspace_id not in seen:
            seen.append(workspace_id)
    return replace(group, workspace_ids=tuple(seen))
