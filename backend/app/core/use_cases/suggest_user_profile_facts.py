"""Suggest candidate profile facts from text — never saves them.

Runs the local model over a conversation (or pasted text) and returns candidate
facts about the user. The caller (the UI) shows them for one-by-one approval;
only then are they persisted via the manage use case. Review-first by design.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.user_profile_extraction import (
    CandidateFact,
    build_extraction_prompt,
    parse_candidates,
)
from app.core.ports.llm_provider_factory import LLMProviderFactoryError
from app.core.ports.user_profile_repository import UserProfileRepositoryPort


class SuggestUserProfileFactsValidationError(ValueError):
    pass


class SuggestUserProfileFactsUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class SuggestUserProfileFactsInput:
    text: str
    max_facts: int = 6


class SuggestUserProfileFactsUseCase:
    def __init__(self, llm_provider_factory, user_profile_repository: UserProfileRepositoryPort) -> None:
        self.llm_provider_factory = llm_provider_factory
        self.user_profile_repository = user_profile_repository

    def suggest(self, request: SuggestUserProfileFactsInput) -> list[CandidateFact]:
        text = (request.text or "").strip()
        if not text:
            raise SuggestUserProfileFactsValidationError("Provide some text to learn from.")

        prompt = build_extraction_prompt(text, max_facts=request.max_facts)
        try:
            provider = self.llm_provider_factory.create(provider=None, model=None)
            raw = provider.generate(prompt)
        except (LLMProviderFactoryError, RuntimeError) as exc:
            raise SuggestUserProfileFactsUnavailableError(
                f"The local model could not suggest facts: {exc}"
            ) from exc

        existing_texts = [item.text for item in self.user_profile_repository.list()]
        return parse_candidates(raw, existing_texts=existing_texts, max_facts=request.max_facts)
