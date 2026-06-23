"""The runtime state store must persist the chosen llama.cpp search/embedding
model independently of the answer model, so the choice survives restarts."""

from app.adapters.system.runtime_state_store import RuntimeStateStore


def test_embedding_ref_round_trips(tmp_path):
    store = RuntimeStateStore(tmp_path / "runtime.json")
    assert store.get_llamacpp_embedding() is None

    store.set_llamacpp_embedding(model_id="qwen3-embedding-0.6b")
    assert store.get_llamacpp_embedding() == {"model_id": "qwen3-embedding-0.6b"}


def test_embedding_and_llm_refs_are_separate(tmp_path):
    store = RuntimeStateStore(tmp_path / "runtime.json")
    store.set_llamacpp_llm(model_id="qwen3-4b")
    store.set_llamacpp_embedding(model_id="bge-m3")

    assert store.get_llamacpp_llm() == {"model_id": "qwen3-4b"}
    assert store.get_llamacpp_embedding() == {"model_id": "bge-m3"}


def test_empty_embedding_ref_is_ignored(tmp_path):
    store = RuntimeStateStore(tmp_path / "runtime.json")
    store.set_llamacpp_embedding()
    assert store.get_llamacpp_embedding() is None
