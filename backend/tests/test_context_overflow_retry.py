"""When the prompt doesn't fit, we send less — and only then admit defeat.

An overflow is our miscount, not a broken engine. The use case must rebuild the
prompt with proportionally less context and ask again; the person should usually
never learn it happened. If the smaller prompt overflows too, the message must
say what was too big — not "check that the engine is running".
"""

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.llm_errors import ContextOverflowError
from app.core.use_cases.ask_workspace_question import (
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionUseCase,
)


class _StrictLLM:
    """An engine with a real limit: it answers a prompt that fits and refuses one
    that doesn't, exactly the way llama-server does — with the numbers attached."""

    provider_name = "llamacpp"
    model_name = "mistral"
    context_window = 8192

    def __init__(self, max_chars: int) -> None:
        self.max_chars = max_chars
        self.prompts: list[str] = []

    def generate(self, prompt, images=None, temperature=None, think=None, history=None):
        self.prompts.append(prompt)
        if len(prompt) > self.max_chars:
            raise ContextOverflowError(
                "the request exceeds the available context size",
                prompt_tokens=8869,
                context_window=8192,
            )
        return "The backend is configured in accounts/account.hcl."


def _uc(**over) -> AskWorkspaceQuestionUseCase:
    uc = AskWorkspaceQuestionUseCase(
        workspace_repository=None,
        embedding_provider=None,
        vector_store=None,
        llm_provider_factory=None,
        index_status_repository=None,
    )
    for key, value in over.items():
        setattr(uc, key, value)
    return uc


def _result(index: int) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=f"ws:doc{index}.md:0",
        source_path=f"doc{index}.md",
        # Cyrillic: the script whose token cost the old budget halved.
        content="як налаштовано бекенд " * 60,
        score=0.9,
        metadata={},
    )


def _request() -> AskWorkspaceQuestionInput:
    return AskWorkspaceQuestionInput(workspace_id="ws", question="як налаштовано бекенд?")


def test_retry_sends_less_context_and_succeeds():
    uc = _uc()
    llm = _StrictLLM(max_chars=15_000)
    chunks = [_result(i) for i in range(20)]
    request = _request()

    # What the attempt that overflowed had sent.
    full, full_prompt, *_ = uc._grounded_prompt(request, llm, chunks, [])
    assert len(full_prompt) > llm.max_chars  # the prompt the engine refused

    retry = uc._retry_with_less_context(
        request,
        llm,
        chunks,
        [],
        ContextOverflowError("too long", prompt_tokens=8869, context_window=8192),
    )

    assert retry is not None
    fitted, prompt, _memory, _facts, _used, answer, _usage = retry
    assert answer.startswith("The backend")
    # Less context than the attempt that overflowed — sized to the overshoot the
    # engine reported, not halved blindly — and this time it fit.
    assert 0 < len(fitted) < len(full)
    assert llm.prompts[-1] == prompt
    assert len(prompt) <= llm.max_chars


def test_a_second_overflow_gives_up_rather_than_looping():
    uc = _uc()
    llm = _StrictLLM(max_chars=0)  # nothing will ever fit

    retry = uc._retry_with_less_context(
        _request(),
        llm,
        [_result(i) for i in range(8)],
        [],
        ContextOverflowError("too long", prompt_tokens=8869, context_window=8192),
    )

    assert retry is None
    # Exactly one extra attempt — no loop.
    assert len(llm.prompts) == 1
