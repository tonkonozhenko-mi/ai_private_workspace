// Human-friendly model labels for chat headers and conversation details.
//
// Raw identifiers like
//   "llamacpp/MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3.Q4_K_M.gguf"
// are accurate but unreadable in the UI. This trims them to
//   "Mistral-7B-Instruct-v0.3 · Q4_K_M — llama.cpp"
// while keeping the full raw string available for tooltips (see rawModelTitle).

const PROVIDER_NAMES: Record<string, string> = {
  llamacpp: "llama.cpp",
  ollama: "Ollama",
};

// Curated llama.cpp catalog ids → a human label ("Name · Quant"). These ids are
// short slugs ("qwen3-4b") that carry no quant/variant, so formatModelLabel can't
// derive a nice label from the string alone. Mirrors backend gguf_catalog.py
// (GGUF_CATALOG); keep the two in sync when the catalog changes. Not applied to
// Ollama, whose tags are already short and use their own quantization.
const CATALOG_MODEL_LABELS: Record<string, string> = {
  "qwen3-4b": "Qwen3 4B Instruct · Q4_K_M",
  "llama3.2": "Llama 3.2 3B Instruct · Q4_K_M",
  "qwen2.5-coder:7b": "Qwen2.5 Coder 7B Instruct · Q4_K_M",
  "nomic-embed-text": "Nomic Embed Text v1.5 · Q4_K_M",
  "bge-m3": "BGE-M3 · Q4_K_M",
  "qwen3-embedding-0.6b": "Qwen3-Embedding 0.6B · Q8_0",
  "bge-reranker-v2-m3": "BGE Reranker v2 m3 · Q4_K_M",
};

function providerDisplay(provider: string | null | undefined): string {
  const key = (provider ?? "").trim();
  if (!key) return "";
  return PROVIDER_NAMES[key.toLowerCase()] ?? key;
}

/**
 * Short display label for an answer/model header.
 * - Drops Hugging Face repo path segments, keeps the file/model name.
 * - Strips a trailing ".gguf" and pulls the quant suffix (Q4_K_M, IQ2_XS, …) out
 *   as a separate fragment.
 * - Leaves already-short Ollama tags ("qwen2.5-coder:7b") untouched.
 */
export function formatModelLabel(
  provider: string | null | undefined,
  model: string | null | undefined,
): string {
  const raw = (model ?? "").trim();
  const providerName = providerDisplay(provider);
  if (!raw) return providerName || "default";

  // A known catalog slug (e.g. "qwen3-4b") has no quant in the string, so resolve
  // it to the curated "Name · Quant" label. Skip Ollama, whose tags are their own.
  const providerKey = (provider ?? "").trim().toLowerCase();
  if (providerKey !== "ollama") {
    const catalogLabel = CATALOG_MODEL_LABELS[raw.toLowerCase()];
    if (catalogLabel) {
      return providerName ? `${catalogLabel} — ${providerName}` : catalogLabel;
    }
  }

  let name = raw.includes("/") ? (raw.split("/").pop() ?? raw) : raw;
  name = name.replace(/\.gguf$/i, "");

  const quantMatch = name.match(/[.\-]((?:IQ|Q)\d[\w]*)$/i);
  if (quantMatch) {
    name = name.slice(0, name.length - quantMatch[0].length);
  }

  const pretty = quantMatch ? `${name} · ${quantMatch[1]}` : name;
  return providerName ? `${pretty} — ${providerName}` : pretty;
}

/** Full raw identifier for tooltips, so no information is lost by the short label. */
export function rawModelTitle(
  provider: string | null | undefined,
  model: string | null | undefined,
): string {
  return `${(provider ?? "").trim()}/${(model ?? "default").trim()}`;
}
