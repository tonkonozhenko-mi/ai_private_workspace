class FakeLLMProvider:
    def generate(self, prompt: str) -> str:
        return f"Fake local LLM response for prompt: {prompt}"
