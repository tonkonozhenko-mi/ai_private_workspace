"""Pulling an Ollama model without a shell, and without a catalog.

The runner itself needs httpx and a daemon, so what is tested here is the part
that decides *whether to start at all* — the guard that used to refuse every
model the app did not already know about.
"""

import pytest

pytest.importorskip("httpx", reason="httpx is a runtime dependency, absent in the pure sandbox")

from app.adapters.system.ollama_pull_job_runner import (  # noqa: E402
    OllamaModelNameInvalidError,
    OllamaPullJobRunner,
)


def test_a_model_the_app_has_never_heard_of_is_allowed():
    """The whole point. `llama3.3` is not in our catalog and never will be —
    keeping up with Ollama's library is not a thing this app should try to do."""
    runner = OllamaPullJobRunner(base_url="http://127.0.0.1:1")  # nothing listening

    job = runner.start("llama3.3")

    assert job.model == "llama3.3"
    assert job.status in ("queued", "running", "failed")


def test_a_name_that_could_not_be_a_model_is_refused_before_any_request():
    runner = OllamaPullJobRunner(base_url="http://127.0.0.1:1")

    for name in ("", "model; rm -rf /", "../../etc/passwd", "http://elsewhere/m"):
        with pytest.raises(OllamaModelNameInvalidError):
            runner.start(name)


def test_an_unreachable_daemon_becomes_a_sentence_about_ollama():
    """Not a transport error. The person did not ask for one and cannot act on it."""
    import time

    runner = OllamaPullJobRunner(base_url="http://127.0.0.1:1")
    job = runner.start("llama3.3")
    for _ in range(50):
        current = runner.get(job.id)
        if current and current.status == "failed":
            break
        time.sleep(0.05)

    current = runner.get(job.id)
    assert current.status == "failed"
    assert "Ollama" in (current.error or "")
