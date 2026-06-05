from hashlib import sha256
import re


EMBEDDING_DIMENSIONS = 128
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_./-]+")


class FakeEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        tokens = TOKEN_PATTERN.findall(text.lower())

        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            for digest_byte in digest[:3]:
                index = digest_byte % EMBEDDING_DIMENSIONS
                vector[index] += 1.0
        return vector
