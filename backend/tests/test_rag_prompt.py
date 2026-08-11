from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag_prompt import SkillPromptInstruction, build_workspace_question_prompt


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

    assert "decide for yourself whether they actually apply" in prompt
    assert "Decide first: is the question about the user's project?" in prompt
    assert "ignore the files and answer directly" in prompt
    assert "name the file it comes from by putting its path in backticks" in prompt
    assert "do NOT append a list of source paths at the end" in prompt
    assert "If multiple files contain relevant configuration, compare them" in prompt
    assert "Available source paths: main.tf" in prompt
    assert "Do not cite only numeric references such as [1] or [2]" in prompt
    # The citation example is a deliberate placeholder, never a plausible
    # filename: models echo the example into answers, and the old `main.tf`
    # seeded a real fabrication (group run, 2026-07-15). Built from the same
    # constant the evaluator ignores, so the two cannot drift apart.
    from app.core.domain.rag_answer_evaluator import CITATION_EXAMPLE_PATH

    assert f"the setting is defined ({CITATION_EXAMPLE_PATH})" in prompt
    assert "main.tf`" not in prompt.split("Available source paths")[1]
    assert "Do not say something is absent if any provided context contains it" in prompt
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


def test_an_instruction_arrives_word_for_word_and_is_still_not_evidence() -> None:
    """Two promises about an instruction, and they pull in opposite directions.

    It must reach the model intact — the person wrote those words on purpose, and
    a prompt that paraphrases them is a control that half-works. And it must not
    become a fact: "pay attention to Jenkins pipelines" is a request about
    emphasis, not a claim that this project has any.

    This test used to pin the heading string of the old block, which is why
    rewording that block broke it while the behaviour it cared about was intact.
    What it pins now is the pair of promises and the boundary between them: the
    not-evidence sentence belongs to the instruction's own block, so it is
    checked as sitting between the instruction and the evidence rather than
    merely existing somewhere in the prompt.
    """
    prompt = build_workspace_question_prompt(
        question="What should I review before deployment?",
        context_results=[
            _context(
                chunk_id="ci-1",
                source_path=".gitlab-ci.yml",
                content="deploy: script: ./deploy.sh",
            )
        ],
        skill_instructions=[
            SkillPromptInstruction(
                name="DevOps",
                instruction="Pay attention to Jenkins pipelines and deployment risks.",
            )
        ],
    )

    assert "- DevOps: Pay attention to Jenkins pipelines and deployment risks." in prompt

    instruction_at = prompt.index("- DevOps: Pay attention")
    not_evidence_at = prompt.index("It is not evidence")
    evidence_at = prompt.index("Context chunks:")

    assert instruction_at < not_evidence_at < evidence_at
    # The disclaimer names where claims may come from, so it cannot be read as
    # a general remark about caution.
    assert "come only from the context chunks" in prompt


def test_the_prompt_states_what_was_never_indexed_when_something_was() -> None:
    """A model cannot notice an absence: unindexed files leave no gap in what it
    is handed. Only this sentence can make it say "that may live in a file I
    never saw" instead of answering confidently from what happened to be there."""
    note = (
        "Note: 14 files with extensions .bicep, .ps1 were not indexed and are "
        "invisible to you; say so if the question may depend on them."
    )

    prompt = build_workspace_question_prompt(
        question="How is the API deployed?",
        context_results=[_context(chunk_id="c1", source_path="README.md", content="Docs.")],
        unread_files_note=note,
    )

    assert note in prompt
    # Before the context, not after: it frames what follows rather than trailing it.
    assert prompt.index(note) < prompt.index("Context chunks:")


def test_the_prompt_says_nothing_when_nothing_was_skipped() -> None:
    """Empty state is silence. A prompt that carries "0 files were skipped" spends
    tokens telling the model that nothing happened."""
    prompt = build_workspace_question_prompt(
        question="How is the API deployed?",
        context_results=[_context(chunk_id="c1", source_path="README.md", content="Docs.")],
    )

    assert "were not indexed" not in prompt
    assert "invisible to you" not in prompt


def test_a_chosen_instruction_outranks_the_role_and_is_read_before_the_evidence():
    """Live: the project role was DevOps, the composer offered Tester / QA, and
    the answer opened "As a DevOps/platform engineer" — quoting the role line
    back. Nothing was miswired: the instruction arrived, and lost.

    It lost because of where it sat and how it spoke. The role said "You are
    reviewing this project as a DevOps engineer" near the top; the instruction sat
    below every context chunk and hedged itself three times — "may shape", "not
    project evidence", "guidance only". A model handed an identity and then a
    suggestion does the obvious thing.

    Two things are pinned here. The instruction is read before the evidence, not
    after it. And the prompt says outright which one wins on emphasis — because
    a control that reports having worked and hasn't is worse than no control."""
    from app.core.domain.indexing import ContextSearchResult
    from app.core.domain.rag_prompt import SkillPromptInstruction, build_workspace_question_prompt

    prompt = build_workspace_question_prompt(
        question="what should I look at first?",
        context_results=[
            ContextSearchResult(
                chunk_id="c1",
                source_path="infra/main.tf",
                content='resource "aws_s3_bucket" "logs" {}',
                score=0.7,
                metadata={},
            )
        ],
        assistant_mode="devops",
        skill_instructions=[
            SkillPromptInstruction(
                name="Security reviewer",
                instruction="Lead with secrets handling and what could leak.",
            )
        ],
    )

    role_at = prompt.index("DevOps/platform engineer")
    instruction_at = prompt.index("Security reviewer")
    evidence_at = prompt.index("Context chunks:")

    assert role_at < instruction_at < evidence_at
    assert "follow this" in prompt.lower()
    # The one hedge worth keeping: an instruction is not a fact about the project.
    # "Focus on secrets handling" must not become "the project handles secrets".
    assert "not evidence" in prompt


def test_without_an_instruction_the_prompt_says_nothing_about_one():
    from app.core.domain.rag_prompt import build_workspace_question_prompt

    prompt = build_workspace_question_prompt(
        question="what should I look at first?",
        context_results=[],
        assistant_mode="devops",
    )

    assert "How to write this answer" not in prompt
