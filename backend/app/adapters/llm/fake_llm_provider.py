class FakeLLMProvider:
    provider_name = "fake"

    def __init__(self, model_name: str = "fake-llm") -> None:
        self.model_name = model_name

    def generate(self, prompt: str, images: list[str] | None = None) -> str:
        image_note = f" Received {len(images)} image(s)." if images else ""
        return (
            "Fake answer generated from the provided workspace context. "
            f"Prompt length: {len(prompt)} characters.{image_note}"
        )
