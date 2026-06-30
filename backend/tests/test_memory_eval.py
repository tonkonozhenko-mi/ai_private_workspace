"""Deterministic evaluation of memory selection (#8): relevant-recall,
stale-usage, and leak (obsolete/forbidden) metrics. Pure; no LLM."""

from app.core.domain.memory_eval import (
    MemoryEvalCase,
    aggregate_memory,
    run_memory_eval,
    score_memory_case,
)
from app.core.domain.project_memory import MemoryItem, MemoryKind, MemoryStatus

RECENT = "2026-06-29T00:00:00+00:00"
OLD = "2026-01-01T00:00:00+00:00"


def _item(
    id_,
    text,
    *,
    kind=MemoryKind.NOTE,
    status=MemoryStatus.ACTIVE,
    stale=False,
    created=RECENT,
    pinned=False,
):
    return MemoryItem(
        id=id_,
        workspace_id="w",
        kind=kind,
        text=text,
        source="user",
        created_at=created,
        pinned=pinned,
        status=status,
        stale=stale,
    )


def test_why_decision_is_recalled():
    items = [
        _item(
            "dec",
            "we use terragrunt because each environment is a separate aws account",
            kind=MemoryKind.ARCHITECTURE_DECISION,
        ),
        _item("noise", "the billing service uses stripe"),
    ]
    score = score_memory_case(
        MemoryEvalCase("why terragrunt", items, expect_relevant_ids=["dec"], forbid_ids=["noise"])
    )
    assert score.passed is True
    assert "dec" in score.recalled_ids
    assert "noise" not in score.recalled_ids


def test_incident_fix_is_recalled():
    items = [
        _item(
            "inc",
            "the prod outage was fixed by raising the worker memory limit",
            kind=MemoryKind.INCIDENT_SOLUTION,
        ),
    ]
    score = score_memory_case(
        MemoryEvalCase("how was the prod outage fixed", items, expect_relevant_ids=["inc"])
    )
    assert score.passed is True
    assert score.relevant_recall == 1.0


def test_obsolete_note_never_leaks():
    items = [
        _item("old", "production is named prod", status=MemoryStatus.OBSOLETE),
        _item("new", "production is actually called prd"),
    ]
    score = score_memory_case(
        MemoryEvalCase(
            "what is production called",
            items,
            expect_relevant_ids=["new"],
            forbid_ids=["old"],
        )
    )
    assert score.passed is True
    assert score.used_obsolete is False
    assert score.leaked_ids == []


def test_stale_note_is_detected_when_recalled():
    items = [_item("s", "main.tf provisions the vpc", stale=True)]
    score = score_memory_case(MemoryEvalCase("vpc main", items, expect_relevant_ids=["s"]))
    assert score.used_stale is True
    assert score.passed is True  # still recalled (it may be true), just flagged


def test_fresh_outranks_stale_at_limit_one():
    items = [
        _item("fresh", "deploy uses github actions", created=RECENT),
        _item("stale", "deploy uses gitlab ci", stale=True, created=OLD),
    ]
    score = score_memory_case(
        MemoryEvalCase(
            "deploy", items, expect_relevant_ids=["fresh"], forbid_ids=["stale"], limit=1
        )
    )
    assert score.recalled_ids == ["fresh"]
    assert score.passed is True


def test_aggregate_metrics_over_a_set():
    obsolete_case = MemoryEvalCase(
        "what is production called",
        [
            _item("old", "production is named prod", status=MemoryStatus.OBSOLETE),
            _item("new", "production is actually called prd"),
        ],
        expect_relevant_ids=["new"],
        forbid_ids=["old"],
    )
    stale_case = MemoryEvalCase(
        "vpc main",
        [_item("s", "main.tf provisions the vpc", stale=True)],
        expect_relevant_ids=["s"],
    )
    report = run_memory_eval([obsolete_case, stale_case])
    assert report.total == 2
    assert report.passed == 2
    assert report.relevant_recall == 1.0
    assert report.stale_usage_rate == 0.5  # one of two cases recalled a stale note
    assert report.leak_rate == 0.0  # nothing obsolete/forbidden leaked


def test_leak_is_counted_when_forbidden_recalled():
    items = [_item("a", "the cache uses redis for sessions")]
    # We (wrongly) forbid the only relevant note, to prove a leak is detected.
    score = score_memory_case(MemoryEvalCase("redis cache", items, forbid_ids=["a"]))
    assert score.leaked_ids == ["a"]
    assert score.passed is False
    report = aggregate_memory([score])
    assert report.leak_rate == 1.0


def test_empty_set_is_safe():
    report = run_memory_eval([])
    assert report.total == 0
    assert report.pass_rate == 0.0
