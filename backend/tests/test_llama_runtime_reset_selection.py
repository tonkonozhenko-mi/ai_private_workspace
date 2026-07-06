"""After a workspace reset, the engine must forget an explicitly chosen answer
model and report the recommended default again (D3)."""

from app.adapters.system.llama_runtime_manager import LlamaRuntimeManager
from app.core.domain.gguf_catalog import default_gguf_llm
from app.core.use_cases.download_gguf_model import GgufModelRef


class _DummyDownload:
    """Stand-in: reset/active-id paths never touch the download use case."""


def _manager() -> LlamaRuntimeManager:
    return LlamaRuntimeManager(_DummyDownload())  # type: ignore[arg-type]


def test_reset_reverts_to_recommended_llm():
    manager = _manager()
    # Explicitly pick a non-recommended catalog model (as a user "switch" would).
    manager.set_llm_ref(GgufModelRef(model_id="llama3.2"))
    assert manager.active_llm_model_id == "llama3.2"

    manager.reset_model_selection()

    assert manager.active_llm_model_id == default_gguf_llm().id
    assert default_gguf_llm().id == "qwen3-4b"  # the recommendation


def test_reset_is_idempotent_and_safe_when_unset():
    manager = _manager()
    # No explicit selection — already on the default; reset must not break it.
    manager.reset_model_selection()
    assert manager.active_llm_model_id == default_gguf_llm().id


def test_reset_llm_only_leaves_the_embedding_model_untouched():
    # A fresh workspace with no answer-model choice resets the LLM to recommended,
    # but must NOT change the search/embedding model (that would invalidate the
    # existing index).
    from app.core.domain.gguf_catalog import default_gguf_embedding

    manager = _manager()
    manager.set_llm_ref(GgufModelRef(model_id="llama3.2"))
    manager.set_embed_ref(GgufModelRef(model_id="bge-m3"))

    manager.reset_llm_selection()

    assert manager.active_llm_model_id == default_gguf_llm().id  # back to recommended
    assert manager.active_embed_model_id == "bge-m3"  # untouched
    assert default_gguf_embedding().id == "nomic-embed-text"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
