"""Deterministic evaluation of memory selection (#8): relevant-recall,
stale-usage, and leak (obsolete/forbidden) metrics. Pure; no LLM."""

from app.core.domain.memory_eval import (
    MemoryEvalCase,
    aggregate_memory,
    run_memory_eval,
    score_memory_case,
)
from app.core.domain.project_memory import MemoryItem, MemoryKind, MemoryStatus
from app.core.use_cases.compose_project_context import ComposeProjectContextUseCase

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


# -- hardened golden categories ---------------------------------------------
# These check real scenarios (not just "did it find the current note"), so the
# harness catches regressions instead of rubber-stamping current behaviour.


class _FakeEmbedder:
    """2-D embedding keyed off marker words, so 'production'/'deploy' notes land
    near a production/deploy question even with no shared keywords (paraphrase)."""

    provider_name = "fake"
    model_name = "fake"

    def embed_text(self, text: str) -> list[float]:
        t = text.lower()
        prod = 1.0 if any(k in t for k in ("prod", "deploy", "ship", "release")) else 0.0
        data = 1.0 if any(k in t for k in ("database", "postgres", "storage", "cache")) else 0.0
        return [prod, data]


class _MemRepo:
    def __init__(self, items):
        self._items = items

    def list(self, workspace_id):
        return self._items


class _GraphRepo:
    def get_latest_graph(self, workspace_id):
        return None


def _semantic_selector(items):
    """A select_fn backed by the real parallel-retrieval path + a fake embedder."""
    uc = ComposeProjectContextUseCase(
        _MemRepo(items), _GraphRepo(), embedding_provider=_FakeEmbedder()
    )
    return lambda its, query, limit: uc._select_memory(its, query, limit)


def test_paraphrase_recall_needs_semantic():
    # Target shares no keywords with the question; recent distractors fill the
    # keyword "most recent" fallback, so keyword-only genuinely misses the target.
    items = [
        _item("p", "we ship code to production every friday", created=OLD),
        _item("d1", "unrelated note about the billing invoice flow", created=RECENT),
        _item("d2", "unrelated note about user avatars", created=RECENT),
    ]
    case = MemoryEvalCase("how do releases reach prod", items, expect_relevant_ids=["p"], limit=2)
    # Keyword-only misses it (no shared tokens); the semantic selector recalls it.
    assert score_memory_case(case).passed is False
    assert score_memory_case(case, _semantic_selector(items)).passed is True


def test_conflict_case_keeps_both_distinct():
    # Two notes, same subject, different values — must not be silently merged.
    items = [
        _item("a", "the database is postgres in production"),
        _item("b", "the database is mysql in staging"),
    ]
    score = score_memory_case(
        MemoryEvalCase("which database?", items, expect_relevant_ids=["a", "b"], limit=6)
    )
    assert set(score.recalled_ids) == {"a", "b"}  # both surfaced, distinct


def test_budget_pressure_keeps_the_pinned_one():
    # Many relevant notes, room for one: the pinned note must win.
    items = [_item(f"n{i}", f"deployment note {i} about the pipeline") for i in range(5)]
    items.append(_item("keep", "deployment pipeline note", pinned=True))
    score = score_memory_case(
        MemoryEvalCase("deployment pipeline", items, expect_relevant_ids=["keep"], limit=1)
    )
    assert score.recalled_ids == ["keep"]


def test_handbook_and_obsolete_never_leak():
    items = [
        _item("hb", "production runs in us-east-1", kind=MemoryKind.HANDBOOK),
        _item("old", "production runs in us-west-2", status=MemoryStatus.OBSOLETE),
        _item("cur", "production runs in eu-central-1"),
    ]
    score = score_memory_case(
        MemoryEvalCase(
            "where does production run",
            items,
            expect_relevant_ids=["cur"],
            forbid_ids=["hb", "old"],
        )
    )
    assert score.passed is True
    assert "hb" not in score.recalled_ids
    assert "old" not in score.recalled_ids


def test_regression_snapshot_exact_order():
    # Pin the exact selection + order for a fixed setup, so any ranking change
    # is caught and reviewed rather than slipping by.
    items = [
        _item("pin", "deploy pipeline", pinned=True, created=OLD),
        _item("fresh", "deploy pipeline runs nightly", created=RECENT),
        _item("old", "deploy pipeline legacy note", created=OLD),
    ]
    score = score_memory_case(MemoryEvalCase("deploy pipeline", items, limit=3))
    assert score.recalled_ids == ["pin", "fresh", "old"]
