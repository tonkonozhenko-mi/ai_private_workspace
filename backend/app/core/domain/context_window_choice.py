"""How much memory can this model be given to remember with?

A model ships with a paper context length — 131,072 tokens for Mistral 7B — and
the app used to ignore it and run everything at a fixed 8192. That is not a
conservative choice, it is an arbitrary one: on a 64 GB machine it throws away
most of what the model could hold, and on an 8 GB machine 8192 might already be
more than the KV cache can afford.

The real limit is arithmetic, not opinion. Every token in the window costs a
fixed number of bytes of KV cache — a property of the architecture, readable from
the model's own metadata — and the machine has a finite amount of RAM, which it
is not ours alone to spend. So: work out what one token costs, work out what we
may spend, divide.

Pure and deterministic; the engines and the UI both read the answer from here.
"""

from __future__ import annotations

# What the KV cache may claim: a quarter of the machine, never more. The rest
# belongs to the model's own weights, the OS, the app, the embedding server, and
# whatever the person was already doing before they opened us.
KV_SHARE_OF_RAM = 0.25
# Held back for everything that is not this model: OS, this app, the embedding
# and reranking servers. Deliberately generous — swapping is worse than a smaller
# window.
RESERVED_BYTES = 6 * 1024**3

# The window is always a multiple of this, so the number we show is a number the
# engine actually loaded.
CONTEXT_STEP = 2048
# Today's behaviour is the floor: it works, and a machine too small for it is
# better served by a smaller model than by a smaller window.
MIN_CONTEXT = 8192
# The ceiling is deliberate. Past ~32k the cost is not only gigabytes: prefill
# time grows with the prompt, and a 32k prompt on CPU or Metal is already tens of
# seconds. Raise it when someone asks for it, not before.
MAX_CONTEXT = 32768

# When a model carries no usable metadata, cost per token is estimated from the
# file size — the one thing we always know. Over-estimating is safe (a smaller
# window), so these numbers lean high.
_FALLBACK_KV_BYTES = (
    (3 * 1024**3, 64 * 1024),
    (6 * 1024**3, 128 * 1024),
)
_FALLBACK_KV_BYTES_LARGE = 192 * 1024

# f16 KV cache: 2 bytes per element, and both a K and a V per layer.
_BYTES_PER_ELEMENT = 2
_K_AND_V = 2


def kv_bytes_per_token(
    *,
    block_count: int | None = None,
    head_count_kv: int | None = None,
    embedding_length: int | None = None,
    head_count: int | None = None,
    model_file_bytes: int = 0,
) -> int:
    """What one token of context costs in KV cache, in bytes.

    ``2 (K and V) × layers × kv_heads × head_dim × 2 (f16)``, where head_dim is
    ``embedding_length / head_count``. For Mistral 7B (32 layers, 8 kv heads,
    4096 / 32 = 128) that is 131,072 bytes — 128 KB a token, which is why a
    128k window would want 16 GB of cache and why we cannot simply grant it.

    Falls back to a size-based estimate when the metadata is missing or nonsense.
    """
    if block_count and head_count_kv and embedding_length and head_count:
        head_dim = embedding_length // head_count
        if head_dim > 0:
            return _K_AND_V * block_count * head_count_kv * head_dim * _BYTES_PER_ELEMENT
    for limit, cost in _FALLBACK_KV_BYTES:
        if model_file_bytes <= limit:
            return cost
    return _FALLBACK_KV_BYTES_LARGE


def choose_context_window(
    *,
    model_max_context: int,
    kv_bytes_per_token: int,
    total_ram_bytes: int,
    model_file_bytes: int,
) -> int:
    """The window this machine can actually afford for this model.

    Never more than the model supports, never more than a quarter of the
    machine's memory, never more than what is left once the weights and a
    reserve for everything else are set aside — and never less than the 8192 we
    have always used, because a machine that cannot afford that needs a smaller
    model, not a smaller memory.
    """
    ceiling = min(model_max_context or MAX_CONTEXT, MAX_CONTEXT)
    # The floor is 8192 — except for a model that cannot hold 8192. A window is a
    # promise to the engine, and the model's own maximum outranks our default.
    floor = min(MIN_CONTEXT, ceiling)
    if total_ram_bytes <= 0 or kv_bytes_per_token <= 0:
        return floor
    free_after_model = total_ram_bytes - model_file_bytes - RESERVED_BYTES
    kv_budget = min(int(total_ram_bytes * KV_SHARE_OF_RAM), free_after_model)
    if kv_budget <= 0:
        return floor
    affordable = kv_budget // kv_bytes_per_token
    window = min(ceiling, affordable)
    window = (window // CONTEXT_STEP) * CONTEXT_STEP
    return max(floor, min(window, MAX_CONTEXT))


def describe_context_window(chosen: int, model_max_context: int | None) -> str:
    """One line for the Models card: the window we run at, and why it is that.

    "Measured, not promised" applies to the window too — if the machine is what
    limits it, the machine should be named.
    """
    tokens = f"{chosen:,} tokens"
    if not model_max_context or model_max_context <= chosen:
        return f"Context: {tokens} (model maximum)"
    return (
        f"Context: {tokens} · model supports {model_max_context:,} — "
        "limited by this computer's memory"
    )


def expected_memory_bytes(
    *,
    model_file_bytes: int,
    kv_bytes_per_token: int,
    context_window: int,
) -> int:
    """What holding this model in memory costs while it answers.

    The same arithmetic that chooses the window, read in the other direction:
    the weights are resident, and the KV cache grows with the window we picked.
    It is the number a person deserves *before* pressing Ask — "running locally
    on your CPU" says the work is local and not what it costs, and the live
    figure only appears once the cost has already been paid.

    Deliberately not padded with a safety margin: an estimate that quietly
    inflates itself is not an estimate, and this one is arithmetic on two facts
    we read from the model file.
    """
    weights = max(0, model_file_bytes)
    cache = max(0, kv_bytes_per_token) * max(0, context_window)
    return weights + cache
