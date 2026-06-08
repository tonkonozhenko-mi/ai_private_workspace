class FakeLLMProvider:
    provider_name = "fake"

    def __init__(self, model_name: str = "fake-llm") -> None:
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        return (
            "Fake answer generated from the provided workspace context. "
            f"Prompt length: {len(prompt)} characters."
        )
