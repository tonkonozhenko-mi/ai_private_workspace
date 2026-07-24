"""A custom answer model chosen in a workspace must survive re-activation.

The regression (0.7.5 beta blocker): a workspace stores its selected model as a
single id string. For a custom model (searched by name or pasted, not in the
static catalog) that id is the composite ``f"{repo_id}/{filename}"``. The
engine-start path passed it to ``set_llm_ref`` as ``model_id`` only, which the
resolver could not match to any catalog entry, so it was silently ignored and
the engine reverted to the recommended default. Live symptom: CURRENT SETUP
showed the chosen model (from config) while the badge and the actual answers came
from the previous/default model.
"""

from app.adapters.system.llama_runtime_manager import LlamaRuntimeManager
from app.core.domain.gguf_catalog import default_gguf_llm
from app.core.use_cases.download_gguf_model import (
    GgufModelRef,
    resolve_gguf_model,
)

CUSTOM_ID = "unsloth/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q4_K_M.gguf"


class _DummyDownload:
    """Stand-in: the id-resolution paths never touch the download use case."""


def _manager() -> LlamaRuntimeManager:
    return LlamaRuntimeManager(_DummyDownload())  # type: ignore[arg-type]


def test_composite_id_resolves_to_repo_and_filename():
    model = resolve_gguf_model(GgufModelRef(model_id=CUSTOM_ID))
    assert model.id == CUSTOM_ID
    assert model.repo_id == "unsloth/Qwen3-0.6B-GGUF"
    assert model.filename == "Qwen3-0.6B-Q4_K_M.gguf"


def test_set_llm_ref_by_composite_id_keeps_the_custom_model():
    # This is exactly what activate_workspace_runtime does with the workspace's
    # stored `.model` string. It must NOT fall back to the recommended default.
    manager = _manager()
    manager.set_llm_ref(GgufModelRef(model_id=CUSTOM_ID))
    assert manager.active_llm_model_id == CUSTOM_ID
    assert manager.active_llm_model_id != default_gguf_llm().id


def test_catalog_ids_still_win_and_are_never_treated_as_custom():
    # A real catalog id resolves to the catalog entry, not a synthesised one.
    model = resolve_gguf_model(GgufModelRef(model_id="qwen3-4b"))
    assert model.quantization != "custom"
    # A colon-tagged catalog id does not end in .gguf, so it is not mis-split.
    assert resolve_gguf_model(GgufModelRef(model_id="qwen2.5-coder:7b")).id == "qwen2.5-coder:7b"


def test_explicit_repo_and_filename_still_win_over_a_bare_id():
    model = resolve_gguf_model(
        GgufModelRef(model_id="ignored", repo_id="acme/Foo-GGUF", filename="foo-Q8_0.gguf")
    )
    assert model.repo_id == "acme/Foo-GGUF"
    assert model.filename == "foo-Q8_0.gguf"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
