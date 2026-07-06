"""Deterministic starter questions for the empty composer (D1)."""

from app.core.domain.project_graph import EntityType, ProjectEntity, ProjectGraph
from app.core.domain.role_lens import role_lens_for
from app.core.domain.starter_questions import GENERIC_STARTERS, starter_questions

_LENS = role_lens_for("developer")


def _graph(entities):
    return ProjectGraph(workspace_id="w", entities=entities)


def _entity(etype, name):
    return ProjectEntity(id=f"{etype}:{name}", type=etype, name=name, analyzer="a")


def test_no_graph_returns_generic_starters():
    assert starter_questions(None, _LENS, limit=4) == list(GENERIC_STARTERS[:4])


def test_empty_graph_returns_generic():
    assert starter_questions(_graph([]), _LENS) == list(GENERIC_STARTERS[:4])


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
