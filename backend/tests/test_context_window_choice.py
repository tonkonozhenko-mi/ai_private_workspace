"""The window is arithmetic, not a constant.

A model's paper context length is what it *could* hold; the machine decides what
it *may*. These pin both halves of that sum, plus the ladder that gives way when
the machine disagrees with our arithmetic.
"""

import struct

from app.adapters.system.gguf_metadata import read_gguf_architecture
from app.core.domain.context_window_choice import (
    MAX_CONTEXT,
    MIN_CONTEXT,
    choose_context_window,
    describe_context_window,
    kv_bytes_per_token,
)

GB = 1024**3

# Mistral 7B: 32 layers, 8 KV heads, 4096 embedding over 32 heads → 128 per head.
MISTRAL = {
    "block_count": 32,
    "head_count_kv": 8,
    "embedding_length": 4096,
    "head_count": 32,
}
MISTRAL_KV = 131_072  # bytes per token — 128 KB, the number behind the 8192 window


# --- what one token costs ------------------------------------------------------


def test_kv_cost_of_mistral_7b_is_128kb_per_token():
    assert kv_bytes_per_token(**MISTRAL) == MISTRAL_KV


def test_kv_cost_falls_back_to_file_size_without_metadata():
    assert kv_bytes_per_token(model_file_bytes=2 * GB) == 64 * 1024
    assert kv_bytes_per_token(model_file_bytes=5 * GB) == 128 * 1024
    assert kv_bytes_per_token(model_file_bytes=20 * GB) == 192 * 1024


def test_incomplete_metadata_is_not_half_trusted():
    # Missing head_count would divide by nothing; fall back rather than invent.
    assert kv_bytes_per_token(block_count=32, head_count_kv=8, model_file_bytes=2 * GB) == 64 * 1024


# --- what the machine may spend ------------------------------------------------


def _mistral_on(ram_gb: int, model_gb: float = 4.4, model_max: int = 131_072) -> int:
    return choose_context_window(
        model_max_context=model_max,
        kv_bytes_per_token=MISTRAL_KV,
        total_ram_bytes=int(ram_gb * GB),
        model_file_bytes=int(model_gb * GB),
    )


def test_a_16gb_mac_gets_a_real_window_not_a_token_one():
    # 25% of 16 GB = 4 GB of KV at 128 KB/token → 32,768 … but the model and the
    # 6 GB reserve leave only ~5.6 GB free, so the cap is the quarter-share: 32k.
    window = _mistral_on(16)
    assert window == 32768
    assert window % 2048 == 0


def test_a_64gb_mac_is_capped_by_the_deliberate_ceiling():
    assert _mistral_on(64) == MAX_CONTEXT


def test_a_small_machine_keeps_the_window_that_always_worked():
    # 8 GB, a 3B model: the reserve eats everything, so we do not shrink below the
    # 8192 that has always worked — that machine needs a smaller model, not a
    # smaller memory.
    assert (
        choose_context_window(
            model_max_context=32768,
            kv_bytes_per_token=64 * 1024,
            total_ram_bytes=8 * GB,
            model_file_bytes=2 * GB,
        )
        == MIN_CONTEXT
    )


def test_the_model_can_be_the_limit_too():
    assert _mistral_on(64, model_max=8192) == 8192


def test_unknown_memory_keeps_todays_behaviour():
    assert (
        choose_context_window(
            model_max_context=131_072,
            kv_bytes_per_token=MISTRAL_KV,
            total_ram_bytes=0,
            model_file_bytes=4 * GB,
        )
        == MIN_CONTEXT
    )


# --- saying which limit is doing the limiting ----------------------------------


def test_the_line_names_the_machine_when_the_machine_is_the_limit():
    assert describe_context_window(16384, 131_072) == (
        "Context: 16,384 tokens · model supports 131,072 — limited by this computer's memory"
    )


def test_the_line_says_so_when_the_model_is_the_limit():
    assert describe_context_window(8192, 8192) == "Context: 8,192 tokens (model maximum)"


# --- reading the model's own description of itself -----------------------------


def _gguf(tmp_path, values: dict[str, int]) -> str:
    """A minimal GGUF header: magic, version, tensor count, then uint32 KV pairs."""
    payload = bytearray(b"GGUF")
    payload += struct.pack("<I", 3)  # version
    payload += struct.pack("<Q", 0)  # tensor count
    payload += struct.pack("<Q", len(values))
    for key, value in values.items():
        encoded = key.encode()
        payload += struct.pack("<Q", len(encoded)) + encoded
        payload += struct.pack("<I", 4)  # uint32
        payload += struct.pack("<I", value)
    path = tmp_path / "model.gguf"
    path.write_bytes(bytes(payload))
    return str(path)


def test_a_gguf_describes_its_own_shape(tmp_path):
    path = _gguf(
        tmp_path,
        {
            "general.architecture_placeholder": 1,
            "llama.context_length": 131072,
            "llama.block_count": 32,
            "llama.embedding_length": 4096,
            "llama.attention.head_count": 32,
            "llama.attention.head_count_kv": 8,
        },
    )
    architecture = read_gguf_architecture(path)
    assert architecture is not None
    assert architecture.context_length == 131072
    assert architecture.head_count_kv == 8
    assert (
        kv_bytes_per_token(
            block_count=architecture.block_count,
            head_count_kv=architecture.head_count_kv,
            embedding_length=architecture.embedding_length,
            head_count=architecture.head_count,
        )
        == MISTRAL_KV
    )


def test_a_file_that_is_not_a_gguf_says_nothing_rather_than_crashing(tmp_path):
    path = tmp_path / "not.gguf"
    path.write_bytes(b"this is not a model")
    assert read_gguf_architecture(path) is None
