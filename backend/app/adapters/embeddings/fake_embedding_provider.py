class FakeEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        if not text:
            return [0.0]
        return [float(len(text)), float(sum(ord(char) for char in text) % 997)]
