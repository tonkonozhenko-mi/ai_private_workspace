from app.core.domain.indexing import ContextSearchResult


def build_workspace_question_prompt(
    question: str,
    context_results: list[ContextSearchResult],
) -> str:
    context_sections = [
        (
            f"Source: {result.source_path}\n"
            f"Chunk ID: {result.chunk_id}\n"
            f"Content:\n{result.content}"
        )
        for result in context_results
    ]
    context = "\n\n---\n\n".join(context_sections)

    return (
        "Answer the workspace question using only the provided context. "
        "If the context is insufficient, say so clearly.\n\n"
        f"Question:\n{question}\n\n"
        f"Context:\n{context}"
    )
