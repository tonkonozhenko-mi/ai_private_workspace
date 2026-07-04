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
