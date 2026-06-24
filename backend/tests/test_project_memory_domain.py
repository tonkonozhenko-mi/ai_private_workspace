"""Project memory selection + handbook builder (pure)."""

from app.core.domain.project_graph import EntityType, ProjectEntity, ProjectFinding, ProjectGraph
from app.core.domain.project_handbook import build_handbook
from app.core.domain.project_memory import (
    MemoryItem,
    MemoryKind,
    format_memory_context,
    select_relevant_memory,
)


def _item(i, kind, text, pinned=False, created="2026-06-01"):
    return MemoryItem(
        id=i,
        workspace_id="w1",
        kind=kind,
        text=text,
        source="user",
        created_at=created,
        pinned=pinned,
    )


def test_select_prefers_pinned_then_overlap():
    items = [
        _item("1", MemoryKind.NOTE, "prod is called prd here", pinned=True),
        _item("2", MemoryKind.NOTE, "database uses postgres", created="2026-06-05"),
        _item("3", MemoryKind.NOTE, "unrelated lunch notes", created="2026-06-09"),
    ]
    res = select_relevant_memory(items, "where is the database configured", limit=6)
    assert res[0].id == "1"  # pinned first
    assert any(r.id == "2" for r in res)  # overlap on 'database'


def test_select_falls_back_to_recent_when_no_overlap():
    items = [
        _item("a", MemoryKind.NOTE, "alpha", created="2026-06-01"),
        _item("b", MemoryKind.NOTE, "beta", created="2026-06-09"),
    ]
    res = select_relevant_memory(items, "zzz nothing matches", limit=6)
    assert res and res[0].id == "b"  # most recent


def test_handbook_excluded_and_format():
    items = [
        _item("h", MemoryKind.HANDBOOK, "the handbook"),
        _item("n", MemoryKind.CORRECTION, "prod is prd", pinned=True),
    ]
    res = select_relevant_memory(items, "prod", limit=6)
    assert all(r.kind != MemoryKind.HANDBOOK for r in res)
    block = format_memory_context(res)
    assert "Correction" in block and "prd" in block


def test_build_handbook_from_graph():
    graph = ProjectGraph(
        workspace_id="w1",
        entities=[
            ProjectEntity(
                id="infra:terraform",
                type=EntityType.INFRA_COMPONENT,
                name="Terraform",
                analyzer="terraform",
            ),
            ProjectEntity(
                id="environment:prod",
                type=EntityType.ENVIRONMENT,
                name="prod",
                analyzer="terraform",
            ),
            ProjectEntity(
                id="cloud_service:aws-lambda",
                type=EntityType.CLOUD_SERVICE,
                name="AWS · Lambda",
                analyzer="terraform",
            ),
        ],
        findings=[
            ProjectFinding(
                id="f1",
                category="reliability",
                severity="high",
                title="No remote state",
                explanation="...",
                analyzer="terraform",
            )
        ],
    )
    hb = build_handbook(graph)
    assert "# Project handbook" in hb
    assert "Terraform" in hb and "prod" in hb and "Lambda" in hb
    assert "No remote state" in hb
