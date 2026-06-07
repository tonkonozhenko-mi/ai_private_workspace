import httpx

from app.core.domain.runtime_health import RuntimeComponentHealth


class QdrantRuntimeHealthChecker:
    def __init__(
        self,
        vector_store: str,
        qdrant_url: str,
        timeout_seconds: float = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self.vector_store = vector_store.lower()
        self.qdrant_url = qdrant_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client()

    def check(self) -> RuntimeComponentHealth:
        if self.vector_store != "qdrant":
            return RuntimeComponentHealth(
                name="qdrant",
                configured=False,
                healthy=True,
                status="not_configured",
                details="Qdrant is not the selected vector store.",
            )

        try:
            response = self.client.get(
                f"{self.qdrant_url}/collections",
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return RuntimeComponentHealth(
                name="qdrant",
                configured=True,
                healthy=False,
                status="unreachable",
                details=f"Qdrant is unreachable at {self.qdrant_url}: {exc}",
            )
        except httpx.HTTPError as exc:
            return RuntimeComponentHealth(
                name="qdrant",
                configured=True,
                healthy=False,
                status="error",
                details=f"Qdrant health request failed at {self.qdrant_url}: {exc}",
            )

        return RuntimeComponentHealth(
            name="qdrant",
            configured=True,
            healthy=True,
            status="ok",
            details=f"Qdrant is reachable at {self.qdrant_url}.",
        )
