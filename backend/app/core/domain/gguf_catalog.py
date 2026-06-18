"""Curated catalog of GGUF models for the llama.cpp (Ollama-free) backend.

Ollama uses registry tags; llama.cpp loads a GGUF file identified by a Hugging
Face ``repo_id`` + ``filename``. Each entry here pairs a friendly name (and,
where it exists, the matching Ollama tag) with the concrete GGUF download, so
the UI can stay "pick a model" regardless of which backend is active.

Model *weights* are plain data and run on any CPU/GPU architecture, so these are
safe to download at runtime. (The architecture-specific ``llama-server`` binary
is bundled with the app, not downloaded — see docs/LLAMACPP_BACKEND_PLAN.md.)
"""

from dataclasses import dataclass

HUGGINGFACE_BASE_URL = "https://huggingface.co"


@dataclass(frozen=True)
class GgufModel:
    id: str  # friendly key, aligned with the Ollama tag where one exists
    name: str
    model_type: str  # "llm" | "embedding" | "reranker"
    repo_id: str
    filename: str
    quantization: str
    size_bytes: int  # approximate download size
    recommended: bool = False
    min_ram_gb: int | None = None
    ollama_tag: str | None = None  # same model on the Ollama backend, if any

    @property
    def download_url(self) -> str:
        return f"{HUGGINGFACE_BASE_URL}/{self.repo_id}/resolve/main/{self.filename}"

    @property
    def relative_storage_path(self) -> str:
        # Stored under <app_data>/models/gguf/<repo>/<file> to avoid collisions.
        safe_repo = self.repo_id.replace("/", "__")
        return f"models/gguf/{safe_repo}/{self.filename}"


# A small, deliberately conservative default set: one light LLM (good on 8 GB),
# one stronger code LLM (16 GB+), and a small embedding model. Quant Q4_K_M is
# the usual size/quality sweet spot.
GGUF_CATALOG: tuple[GgufModel, ...] = (
    GgufModel(
        id="llama3.2",
        name="Llama 3.2 3B Instruct",
        model_type="llm",
        repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
        filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        quantization="Q4_K_M",
        size_bytes=2_020_000_000,
        recommended=True,
        min_ram_gb=8,
        ollama_tag="llama3.2",
    ),
    GgufModel(
        id="qwen2.5-coder:7b",
        name="Qwen2.5 Coder 7B Instruct",
        model_type="llm",
        repo_id="bartowski/Qwen2.5-Coder-7B-Instruct-GGUF",
        filename="Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
        quantization="Q4_K_M",
        size_bytes=4_680_000_000,
        recommended=False,
        min_ram_gb=16,
        ollama_tag="qwen2.5-coder:7b",
    ),
    GgufModel(
        id="nomic-embed-text",
        name="Nomic Embed Text v1.5",
        model_type="embedding",
        repo_id="nomic-ai/nomic-embed-text-v1.5-GGUF",
        filename="nomic-embed-text-v1.5.Q4_K_M.gguf",
        quantization="Q4_K_M",
        size_bytes=84_000_000,
        recommended=True,
        min_ram_gb=8,
        ollama_tag="nomic-embed-text",
    ),
    GgufModel(
        id="bge-reranker-v2-m3",
        name="BGE Reranker v2 m3",
        model_type="reranker",
        repo_id="gpustack/bge-reranker-v2-m3-GGUF",
        filename="bge-reranker-v2-m3-Q4_K_M.gguf",
        quantization="Q4_K_M",
        size_bytes=370_000_000,
        recommended=True,
        min_ram_gb=8,
    ),
)


def list_gguf_models(model_type: str | None = None) -> list[GgufModel]:
    if model_type is None:
        return list(GGUF_CATALOG)
    return [model for model in GGUF_CATALOG if model.model_type == model_type]


def find_gguf_model(model_id: str) -> GgufModel | None:
    key = (model_id or "").strip().lower()
    for model in GGUF_CATALOG:
        if model.id.lower() == key:
            return model
    return None


def default_gguf_llm() -> GgufModel:
    for model in GGUF_CATALOG:
        if model.model_type == "llm" and model.recommended:
            return model
    return next(model for model in GGUF_CATALOG if model.model_type == "llm")


def default_gguf_embedding() -> GgufModel:
    for model in GGUF_CATALOG:
        if model.model_type == "embedding" and model.recommended:
            return model
    return next(model for model in GGUF_CATALOG if model.model_type == "embedding")


def default_gguf_reranker() -> GgufModel:
    for model in GGUF_CATALOG:
        if model.model_type == "reranker" and model.recommended:
            return model
    return next(model for model in GGUF_CATALOG if model.model_type == "reranker")
