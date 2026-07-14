"""The benchmark must be reproducible on both engines the app ships.

The app ships llama.cpp and Ollama; the benchmark generated answers on Ollama
only, so half the readers could not reproduce the published table — and "run it
yourself" is the whole claim. The generation engine is now a flag, the report
carries its own suffix so a llama.cpp run is a second column rather than a
replacement, and every answer records how long it took: one Terraform question
was slow enough to look like a bug, and "it is slow" is not an answer. A number
is.
"""

import httpx
import pytest

from eval.golden import LlamaServerNotRunning, _build_llm
from eval.golden_set import CLASS_PROJECT_PRECISE, QuestionCase
from eval.harness import QuestionOutcome, compute_report, render_markdown, report_to_dict

CASES = [
    QuestionCase("pp-a", "Where is the VPC defined?", CLASS_PROJECT_PRECISE, ("main.tf",)),
    QuestionCase("pp-b", "Where are the endpoints?", CLASS_PROJECT_PRECISE, ("endpoints.tf",)),
]


def _outcome(qid: str, seconds: float | None) -> QuestionOutcome:
    return QuestionOutcome(
        question_id=qid,
        abstained=False,
        source_paths=("main.tf",),
        best_score=0.7,
        hallucinated=False,
        raw_hallucinated=False,
        generation_seconds=seconds,
    )


# --- the engine is a choice, and a missing one says so --------------------------


def test_the_ollama_path_is_unchanged():
    llm = _build_llm("http://localhost:11434", "qwen3:4b", "ollama", "http://127.0.0.1:8080")
    assert llm.provider_name == "ollama"
    assert llm.base_url == "http://localhost:11434"
    assert llm.timeout_seconds == 360  # same budget on both engines, or no comparison


def test_llamacpp_generation_talks_to_the_llama_server(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, timeout=5: httpx.Response(200))
    llm = _build_llm("http://localhost:11434", "qwen3", "llamacpp", "http://127.0.0.1:8080")
    assert llm.provider_name == "llamacpp"
    assert llm.base_url == "http://127.0.0.1:8080"
    assert llm.timeout_seconds == 360


def test_a_missing_llama_server_says_what_to_start(monkeypatch):
    def refuse(url, timeout=5):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", refuse)
    with pytest.raises(LlamaServerNotRunning) as caught:
        _build_llm("http://localhost:11434", "qwen3", "llamacpp", "http://127.0.0.1:8080")
    message = str(caught.value)
    assert "http://127.0.0.1:8080" in message
    assert "Start the" in message  # a setup instruction, not a traceback


# --- the timing reaches both reports -------------------------------------------


def test_generation_seconds_are_summarised_and_published():
    outcomes = [_outcome("pp-a", 12.0), _outcome("pp-b", 300.0)]
    report = compute_report("nomic-llamacpp-gen", 5, CASES, outcomes)

    assert report.generation_seconds_p50 == 156.0  # the median of two is their mean
    assert report.generation_seconds_max == 300.0

    data = report_to_dict(report, CASES, outcomes)
    assert data["overall"]["generation_seconds_max"] == 300.0
    per_question = {q["id"]: q for q in data["questions"]}
    assert per_question["pp-b"]["generation_seconds"] == 300.0

    markdown = render_markdown(report, CASES, outcomes)
    assert "Generation seconds" in markdown
    assert "300.0s" in markdown


def test_a_retrieval_only_run_publishes_no_timings():
    outcomes = [_outcome("pp-a", None), _outcome("pp-b", None)]
    report = compute_report("nomic", 5, CASES, outcomes)
    assert report.generation_seconds_p50 is None
    assert "Generation seconds" not in render_markdown(report, CASES, outcomes)
