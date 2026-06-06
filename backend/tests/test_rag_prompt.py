from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag_prompt import build_workspace_question_prompt


def test_rag_prompt_labels_multiple_context_chunks_with_source_paths() -> None:
    prompt = build_workspace_question_prompt(
        question="How is the Terraform backend configured?",
        context_results=[
            _context(
                chunk_id="terragrunt-1",
                source_path="terragrunt.hcl",
                content='remote_state { backend = "s3" }',
            ),
            _context(
                chunk_id="terraform-1",
                source_path="main.tf",
                content='terraform { backend "s3" {} }',
            ),
        ],
    )

    assert "[1] source_path: terragrunt.hcl" in prompt
    assert "[2] source_path: main.tf" in prompt
    assert "chunk_id: terragrunt-1" in prompt
    assert "chunk_id: terraform-1" in prompt
    assert 'remote_state { backend = "s3" }' in prompt
    assert 'terraform { backend "s3" {} }' in prompt


def test_rag_prompt_requires_grounded_source_aware_answer() -> None:
    prompt = build_workspace_question_prompt(
        question="How is the backend configured?",
        context_results=[
            _context(
                chunk_id="terraform-1",
                source_path="main.tf",
                content='terraform { backend "s3" {} }',
            )
        ],
    )

    assert "Use only the provided context chunks" in prompt
    assert "Always mention source_path when making a technical claim" in prompt
    assert "If multiple files contain relevant configuration, compare them" in prompt
    assert (
        "Do not say something is absent if any provided context contains it" in prompt
    )
    assert "If the context is insufficient or you are unsure" in prompt
    assert "Answer requirements:" in prompt
    assert "Start with a direct answer" in prompt
    assert "Do not invent facts" in prompt


def _context(
    chunk_id: str,
    source_path: str,
    content: str,
) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=chunk_id,
        source_path=source_path,
        content=content,
        score=1.0,
        metadata={},
    )
