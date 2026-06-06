class FakeLLMProvider:
    provider_name = "fake"
    model_name = "fake-llm"

    def generate(self, prompt: str) -> str:
        return (
            "Fake answer generated from the provided workspace context. "
            f"Prompt length: {len(prompt)} characters."
        )
