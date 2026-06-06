from app.adapters.vector_store.qdrant_collection_naming import (
    MAX_QDRANT_COLLECTION_NAME_LENGTH,
    build_qdrant_collection_name,
)


def test_collection_name_falls_back_to_base_without_embedding_metadata() -> None:
    assert build_qdrant_collection_name("ai_workbench_chunks") == "ai_workbench_chunks"


def test_fake_embedding_metadata_creates_expected_collection_name() -> None:
    collection_name = build_qdrant_collection_name(
        base_collection_name="ai_workbench_chunks",
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=128,
    )

    assert collection_name == "ai_workbench_chunks_fake_fake_embedding_128"


def test_ollama_embedding_metadata_creates_expected_collection_name() -> None:
    collection_name = build_qdrant_collection_name(
        base_collection_name="AI Workbench Chunks",
        embedding_provider="Ollama",
        embedding_model="nomic-embed-text",
        embedding_dimension=768,
    )

    assert collection_name == "ai_workbench_chunks_ollama_nomic_embed_text_768"


def test_collection_name_sanitization_collapses_characters_and_limits_length() -> None:
    collection_name = build_qdrant_collection_name(
        base_collection_name="AI---Workbench///Chunks",
        embedding_provider="Local Ollama",
        embedding_model="model/" + ("very-long-" * 40),
        embedding_dimension=1024,
    )

    assert "---" not in collection_name
    assert "/" not in collection_name
    assert "__" not in collection_name
    assert len(collection_name) <= MAX_QDRANT_COLLECTION_NAME_LENGTH
