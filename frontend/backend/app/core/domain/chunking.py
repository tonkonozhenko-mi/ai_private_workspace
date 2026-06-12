DEFAULT_CHUNK_MAX_CHARS = 1200
DEFAULT_CHUNK_OVERLAP_CHARS = 150


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap must be zero or greater")
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")

    stripped_text = text.strip()
    if not stripped_text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(stripped_text):
        end = min(start + max_chars, len(stripped_text))
        chunk = stripped_text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(stripped_text):
            break
        start = end - overlap

    return chunks


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
