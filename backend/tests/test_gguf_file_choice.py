"""Choosing a file out of a Hugging Face GGUF repository.

These rules used to live inside an HTTP route, so none of them could be tested
without a network, and the one rule the route could not enforce — skip builds for
accelerators we cannot use — was printed in the interface as advice: "avoid repos
tagged npu/mobilint". This file is that advice becoming code.
"""

from app.core.domain.gguf_file_choice import (
    QUANT_PREFERENCE,
    choose_gguf_file,
    describe_quantization,
    is_runnable_model_file,
    quantization_of,
    rank_candidates,
    unusable_reason,
)

# What a real repository looks like: one model, many builds, and some files that
# are not the model.
REPO = [
    "Qwen3-8B-Q2_K.gguf",
    "Qwen3-8B-Q4_K_M.gguf",
    "Qwen3-8B-Q4_K_S.gguf",
    "Qwen3-8B-Q8_0.gguf",
    "Qwen3-8B-f16.gguf",
    "Qwen3-8B-vocab.gguf",
    "mmproj-Qwen3-8B-f16.gguf",
    "README.md",
]


def test_the_usual_choice_wins_by_default():
    assert choose_gguf_file(REPO) == "Qwen3-8B-Q4_K_M.gguf"


def test_files_that_are_not_a_model_are_never_offered():
    names = {c.filename for c in rank_candidates(REPO)}

    assert "Qwen3-8B-vocab.gguf" not in names
    assert "mmproj-Qwen3-8B-f16.gguf" not in names
    assert "README.md" not in names


def test_builds_for_hardware_we_cannot_use_are_filtered_not_explained_to_the_user():
    """The interface used to ask people to avoid these by hand. It shouldn't
    have to know they exist."""
    for name in (
        "Qwen3-8B-npu-Q4_K_M.gguf",
        "Qwen3-8B-mobilint.gguf",
        "Qwen3-8B-rknn-Q4_0.gguf",
    ):
        assert not is_runnable_model_file(name), name

    assert choose_gguf_file(["Qwen3-8B-npu.gguf", "Qwen3-8B-Q4_K_M.gguf"]) == "Qwen3-8B-Q4_K_M.gguf"


def test_a_split_model_is_not_offered_because_we_download_one_file():
    assert not is_runnable_model_file("Qwen3-235B-Q4_K_M-00001-of-00005.gguf")


def test_every_candidate_carries_what_the_choice_costs():
    candidates = rank_candidates(REPO)

    by_quant = {c.quantization: c.trade_off for c in candidates}
    assert "usual choice" in by_quant["Q4_K_M"]
    assert "Smallest" in by_quant["Q2_K"]
    assert "twice the memory" in by_quant["Q8_0"]
    assert "unquantized" in by_quant["F16"]


def test_exactly_one_candidate_is_recommended_and_it_is_the_first():
    candidates = rank_candidates(REPO)

    recommended = [c for c in candidates if c.recommended]
    assert len(recommended) == 1
    assert recommended[0] is candidates[0]
    assert recommended[0].filename == "Qwen3-8B-Q4_K_M.gguf"


def test_asking_for_a_quantization_gets_that_one():
    assert choose_gguf_file(REPO, "q8_0") == "Qwen3-8B-Q8_0.gguf"


def test_asking_for_one_the_repo_does_not_have_falls_back_rather_than_failing():
    """Refusing outright would be correct and useless: the person wants this
    model, and the repository simply doesn't publish that build."""
    assert choose_gguf_file(REPO, "q3_k_l") == "Qwen3-8B-Q4_K_M.gguf"


def test_sizes_are_carried_when_known_and_absent_when_not():
    with_sizes = rank_candidates([("Qwen3-8B-Q4_K_M.gguf", 4_920_000_000)])
    without = rank_candidates(["Qwen3-8B-Q4_K_M.gguf"])

    assert with_sizes[0].size_bytes == 4_920_000_000
    # Hugging Face only reports sizes when asked; not knowing must not stop the
    # person from choosing.
    assert without[0].size_bytes == 0
    assert without[0].filename == "Qwen3-8B-Q4_K_M.gguf"


def test_quantization_is_read_out_of_the_filename():
    assert quantization_of("Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf") == "Q5_K_M"
    assert quantization_of("model.f16.gguf") == "F16"
    assert quantization_of("model.gguf") == ""
    assert describe_quantization("") == ""


# --- when nothing fits, say which kind of nothing -----------------------------


def test_a_repo_without_gguf_says_it_is_probably_the_original_model():
    reason = unusable_reason(["config.json", "model.safetensors"])

    assert "no GGUF files" in reason
    assert "GGUF" in reason  # …and points at what to look for instead


def test_a_split_model_says_so_rather_than_blaming_the_repo():
    reason = unusable_reason(["Qwen3-235B-Q4_K_M-00001-of-00005.gguf"])

    assert "split across several files" in reason


def test_an_accelerator_only_repo_says_right_model_wrong_build():
    reason = unusable_reason(["Qwen3-8B-npu.gguf"])

    assert "hardware this app does not use" in reason


def test_nothing_in_nothing_out():
    assert rank_candidates([]) == []
    assert rank_candidates(None) == []
    assert choose_gguf_file([]) == ""


def test_the_preference_order_still_leads_with_the_catalog_default():
    """The bundled catalog ships Q4_K_M. If this list ever stops agreeing with
    it, a custom model would behave differently from a catalog one for no
    reason a person could see."""
    assert QUANT_PREFERENCE[0] == "q4_k_m"
