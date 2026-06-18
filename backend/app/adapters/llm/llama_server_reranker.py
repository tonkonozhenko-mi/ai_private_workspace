"""Cross-encoder reranker backed by a local ``llama-server --reranking`` process.

llama.cpp's server exposes a ``/rerank`` endpoint that scores each (query,
document) pair with a reranker model (e.g. bge-reranker). We send the top
candidates from hybrid retrieval and reorder by the returned relevance score.

Every failure path (disabled, server down, bad response) falls back to the input
order, so enabling this can never break Ask — at worst it's a no-op.
"""

import httpx


class LlamaServerReranker:
    def __init__(
        self,
        base_url: str,
        model: str,
        enabled: bool = False,
        timeout_seconds: int = 60,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[int]:
        identity = list(range(len(documents)))[: max(0, top_k)]
        if not self._enabled or not query.strip() or len(documents) <= 1 or top_k <= 0:
            return identity
        try:
            response = self.client.post(
                f"{self.base_url}/rerank",
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k,
                },
                timeout=self.timeout_seconds,
            )
            if response.status_code >= 400:
                return identity
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return identity

        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or not results:
            return identity

        ranked: list[tuple[float, int]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            score = item.get("relevance_score", item.get("score"))
            if (
                isinstance(index, int)
                and 0 <= index < len(documents)
                and isinstance(score, int | float)
                and not isinstance(score, bool)
            ):
                ranked.append((float(score), index))
        if not ranked:
            return identity
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [index for _, index in ranked][:top_k]
