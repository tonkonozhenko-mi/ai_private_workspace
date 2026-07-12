"""Deterministic starter questions for the empty composer (D1)."""

from dataclasses import replace

from app.core.domain.project_graph import EntityType, ProjectEntity, ProjectGraph
from app.core.domain.role_lens import role_lens_for
from app.core.domain.starter_questions import (
    GENERIC_STARTERS,
    ROLE_STARTERS,
    starter_questions,
)

_LENS = role_lens_for("developer")


def _graph(entities):
    return ProjectGraph(workspace_id="w", entities=entities)


def _entity(etype, name):
    return ProjectEntity(id=f"{etype}:{name}", type=etype, name=name, analyzer="a")


def test_no_graph_falls_back_to_the_role_openers():
    # Before a map exists the questions can't come from facts — but they can still
    # come from the person asking.
    assert starter_questions(None, _LENS, limit=4) == list(ROLE_STARTERS["developer"][:4])
    assert starter_questions(None, role_lens_for("tester"), limit=4) == list(
        ROLE_STARTERS["tester"][:4]
    )


def test_empty_graph_falls_back_to_the_role_openers():
    assert starter_questions(_graph([]), _LENS) == list(ROLE_STARTERS["developer"][:4])


def test_an_unknown_role_falls_back_to_the_generic_set():
    lens = role_lens_for("developer")
    unknown = replace(lens, role="something_new")
    assert starter_questions(None, unknown, limit=4) == list(GENERIC_STARTERS[:4])


def test_map_derived_questions_are_evidence_gated():
    # A pipeline present → a deploy/CI question should surface (map-derived).
    graph = _graph(
        [
            _entity(EntityType.PIPELINE, "ci.yml"),
            _entity(EntityType.ENVIRONMENT, "prod"),
        ]
    )
    questions = starter_questions(graph, _LENS, limit=4)
    assert questions  # non-empty
    assert len(questions) <= 4
    joined = " ".join(questions).lower()
    assert "deploy" in joined or "ci" in joined or "environment" in joined


def test_limit_is_respected():
    graph = _graph(
        [
            _entity(EntityType.PIPELINE, "ci.yml"),
            _entity(EntityType.ENVIRONMENT, "prod"),
            _entity(EntityType.INFRA_COMPONENT, "aws_s3"),
            _entity(EntityType.CLOUD_SERVICE, "S3"),
            _entity(EntityType.SERVICE, "api"),
        ]
    )
    assert len(starter_questions(graph, _LENS, limit=3)) == 3
