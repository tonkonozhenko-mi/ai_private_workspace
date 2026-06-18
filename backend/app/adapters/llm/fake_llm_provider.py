class FakeLLMProvider:
    provider_name = "fake"

    def __init__(self, model_name: str = "fake-llm") -> None:
        self.model_name = model_name

    def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> str:
        image_note = f" Received {len(images)} image(s)." if images else ""
        return (
            "Fake answer generated from the provided workspace context. "
            f"Prompt length: {len(prompt)} characters.{image_note}"
        )

    def generate_stream(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
    ):
        # Stream the canned answer word-by-word so streaming code paths and the
        # UI can be exercised without a real model.
        answer = self.generate(prompt, images, temperature, think, history)
        for index, word in enumerate(answer.split(" ")):
            yield word if index == 0 else f" {word}"
