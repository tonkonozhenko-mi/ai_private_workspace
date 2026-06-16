import re
from hashlib import sha256

MAX_QDRANT_COLLECTION_NAME_LENGTH = 255
NON_ALPHANUMERIC_PATTERN = re.compile(r"[^a-z0-9]+")


def build_qdrant_collection_name(
    base_collection_name: str,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
) -> str:
    if not embedding_provider or not embedding_model or embedding_dimension is None:
        return base_collection_name

    collection_name = "_".join(
        [
            _sanitize_component(base_collection_name),
            _sanitize_component(embedding_provider),
            _sanitize_component(embedding_model),
            str(embedding_dimension),
        ]
    )
    if len(collection_name) <= MAX_QDRANT_COLLECTION_NAME_LENGTH:
        return collection_name

    digest = sha256(collection_name.encode("utf-8")).hexdigest()[:12]
    prefix_length = MAX_QDRANT_COLLECTION_NAME_LENGTH - len(digest) - 1
    return f"{collection_name[:prefix_length].rstrip('_')}_{digest}"


def _sanitize_component(value: str) -> str:
    sanitized = NON_ALPHANUMERIC_PATTERN.sub("_", value.lower()).strip("_")
    return sanitized or "unknown"
