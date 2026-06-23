"""The install guide must offer every real answer/search model — including the
newer embedders — and never the fake dev models."""

from app.core.domain.local_model_install_guide import build_local_model_install_guide
from app.core.domain.model_catalog_registry import DEFAULT_LOCAL_MODELS


def _guide():
    return build_local_model_install_guide(list(DEFAULT_LOCAL_MODELS))


def test_new_embedders_are_installable():
    models = {o.model for o in _guide().options}
    assert "nomic-embed-text" in models
    assert "bge-m3" in models
    assert "qwen3-embedding:0.6b" in models


def test_fake_models_are_never_offered():
    providers = {o.model for o in _guide().options}
    assert "fake-llm" not in providers
    assert "fake-embedding" not in providers


def test_each_option_has_a_pull_command():
    for option in _guide().options:
        assert option.install_command.startswith("ollama pull ")


def test_embedders_describe_their_difference():
    by_model = {o.model: o.purpose for o in _guide().options}
    assert "ultilingual" in by_model["bge-m3"]  # "Multilingual"
    assert "ccurate" in by_model["qwen3-embedding:0.6b"]  # "accurate"
