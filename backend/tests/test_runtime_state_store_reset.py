"""A full workspace reset must forget the persisted answer/search model refs so
the engine falls back to the recommended defaults instead of resurrecting the
last-lived model (D3). ``active_backend`` and other keys must survive."""

import tempfile
from pathlib import Path

from app.adapters.system.runtime_state_store import RuntimeStateStore


def test_clear_llamacpp_models_removes_both_refs():
    with tempfile.TemporaryDirectory() as d:
        store = RuntimeStateStore(Path(d) / "runtime.json")
        store.set_llamacpp_llm(model_id="mistral")
        store.set_llamacpp_embedding(model_id="bge-m3")

        store.clear_llamacpp_models()

        assert store.get_llamacpp_llm() is None
        assert store.get_llamacpp_embedding() is None


def test_clear_llamacpp_models_keeps_active_backend():
    with tempfile.TemporaryDirectory() as d:
        store = RuntimeStateStore(Path(d) / "runtime.json")
        store.set_active_backend("llamacpp")
        store.set_llamacpp_llm(model_id="mistral")

        store.clear_llamacpp_models()

        # The engine choice survives — only the specific model refs are cleared,
        # so a fresh engine just starts on the recommended defaults.
        assert store.get_active_backend() == "llamacpp"
        assert store.get_llamacpp_llm() is None


def test_clear_llamacpp_models_is_safe_when_empty():
    with tempfile.TemporaryDirectory() as d:
        store = RuntimeStateStore(Path(d) / "runtime.json")
        # No file written yet, and no refs saved — clearing must not raise.
        store.clear_llamacpp_models()
        assert store.get_llamacpp_llm() is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
