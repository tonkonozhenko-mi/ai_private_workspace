"""The labelled golden question set.

Written against THIS repository (a stable, always-available target) so the
expected source paths are real and don't drift. Three classes:

- ``project_precise``: a specific answer lives in specific file(s); retrieval
  should surface at least one of ``expected_paths`` in the top-k.
- ``project_broad``: an "about the whole project" question; any grounded answer
  (>=1 source, not abstained) counts — these lean on the handbook pseudo-doc.
- ``should_abstain``: NOT about the project (chit-chat, world facts, time); the
  right behaviour is to abstain and return ZERO project sources. Includes Fable's
  live regression "what time is it", which on nomic wrongly scored above the cap.

``expected_paths`` are matched as path suffixes/substrings, so "parent_document.py"
matches "backend/app/core/domain/parent_document.py". Extend freely; add other
repos by writing a second set and pointing the runner at that repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CLASS_PROJECT_PRECISE = "project_precise"
CLASS_PROJECT_BROAD = "project_broad"
CLASS_SHOULD_ABSTAIN = "should_abstain"


@dataclass(frozen=True)
class QuestionCase:
    id: str
    question: str
    cls: str
    # Path suffixes any of which, if present in a retrieved source path, counts as
    # a retrieval hit (project_precise only).
    expected_paths: tuple[str, ...] = field(default_factory=tuple)

    @property
    def should_abstain(self) -> bool:
        return self.cls == CLASS_SHOULD_ABSTAIN


# NOTE: keep questions phrased the way a real user would ask, not as keyword
# queries — the point is to test retrieval on natural language.
GOLDEN_SET: tuple[QuestionCase, ...] = (
    # --- project_precise ------------------------------------------------
    QuestionCase(
        "pp-parent-doc",
        "How does the parent-document expansion grow a retrieved chunk with its neighbours?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/parent_document.py",),
    ),
    QuestionCase(
        "pp-quote-check",
        "Where do we verify that a quote in the answer actually appears in the sources?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/rag_answer_evaluator.py",),
    ),
    QuestionCase(
        "pp-crag",
        "How does the corrective retrieval pass (CRAG-lite) decide to retry?",
        CLASS_PROJECT_PRECISE,
        ("core/use_cases/ask_workspace_question.py",),
    ),
    QuestionCase(
        "pp-full-context",
        "When does Ask skip retrieval and feed the whole project instead?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/context_budget.py", "core/use_cases/ask_workspace_question.py"),
    ),
    QuestionCase(
        "pp-noise-floor",
        "How is the abstention relevance floor calibrated to the embedding model?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/relevance_calibration.py",),
    ),
    QuestionCase(
        "pp-mmr",
        "How does MMR pick a diverse-but-relevant subset of chunks?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/mmr.py",),
    ),
    QuestionCase(
        "pp-chunking",
        "How are very long single lines split during chunking?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/chunking.py",),
    ),
    QuestionCase(
        "pp-per-file-cap",
        "How do we stop one file from dominating the retrieved context?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/retrieval_diversity.py",),
    ),
    QuestionCase(
        "pp-hybrid-search",
        "How does the SQLite vector store combine dense and keyword search?",
        CLASS_PROJECT_PRECISE,
        ("adapters/vector_store/sqlite_vector_store.py",),
    ),
    QuestionCase(
        "pp-incremental",
        "How does the incremental re-index decide which files to re-embed?",
        CLASS_PROJECT_PRECISE,
        ("core/use_cases/index_workspace.py",),
    ),
    QuestionCase(
        "pp-handbook-pseudo",
        "How is the project handbook indexed as a pseudo-document?",
        CLASS_PROJECT_PRECISE,
        ("core/use_cases/index_workspace.py",),
    ),
    QuestionCase(
        "pp-csp",
        "What Content-Security-Policy does the desktop app set?",
        CLASS_PROJECT_PRECISE,
        ("tauri.conf.json",),
    ),
    QuestionCase(
        "pp-context-budget",
        "How is the character budget for retrieved chunks computed from the window?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/context_budget.py",),
    ),
    QuestionCase(
        "pp-answer-modes",
        "How do the answer modes change what gets retrieved?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/rag_prompt.py",),
    ),
    QuestionCase(
        "pp-query-rewrite",
        "How is the search query rewritten before retrieval?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/rag_query_rewrite.py",),
    ),
    QuestionCase(
        "pp-investigator",
        "How does the investigator agent parse a ReAct step?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/investigator.py",),
    ),
    QuestionCase(
        "pp-source-chunks",
        "How does the vector store return all chunks of one file in order?",
        CLASS_PROJECT_PRECISE,
        ("adapters/vector_store/",),
    ),
    QuestionCase(
        "pp-intent",
        "How do we decide whether a question looks project-specific?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/question_intent.py",),
    ),
    QuestionCase(
        "pp-memory-handbook",
        "How is the deterministic project handbook built from the map?",
        CLASS_PROJECT_PRECISE,
        ("core/domain/project_handbook.py", "core/use_cases/build_project_handbook.py"),
    ),
    QuestionCase(
        "pp-manifest",
        "How does the index manifest track what is already indexed?",
        CLASS_PROJECT_PRECISE,
        ("index_manifest", "adapters/memory/"),
    ),
    # --- project_broad --------------------------------------------------
    QuestionCase("pb-what", "What is this project about?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-arch", "Give me an overview of the architecture.", CLASS_PROJECT_BROAD),
    QuestionCase("pb-stack", "What technologies and languages does this project use?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-start", "Where should a new developer start reading the code?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-rag", "How does the RAG pipeline work end to end?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-run", "How do I run this project locally?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-tests", "How is the project tested?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-ports", "How is the backend structured (ports and adapters)?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-privacy", "What makes this project local-first and private?", CLASS_PROJECT_BROAD),
    QuestionCase("pb-changed", "What changed recently in the project?", CLASS_PROJECT_BROAD),
    # --- should_abstain (NOT about the project) -------------------------
    QuestionCase("sa-time", "What time is it?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-weather", "What's the weather like today?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-hello", "Hello, how are you doing?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-capital", "What is the capital of France?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-worldcup", "Who won the last football World Cup?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-joke", "Tell me a joke.", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-math", "What is 17 times 23?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-recipe", "How do I make a good carbonara?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-python-generic", "What is a Python decorator in general?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("sa-thanks", "Thanks, that was helpful!", CLASS_SHOULD_ABSTAIN),
)


def golden_set() -> tuple[QuestionCase, ...]:
    return GOLDEN_SET
