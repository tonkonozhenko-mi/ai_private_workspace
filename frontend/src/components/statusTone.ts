export type StatusTone =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "neutral"
  | "accent";

const SUCCESS_LABELS = new Set([
  "ready",
  "indexed",
  "done",
  "available",
  "success",
  "completed",
  "no reindex",
  "no restart",
  "shared context",
  "local llm calls",
]);

const WARNING_LABELS = new Set([
  "recommended",
  "needed",
  "needs setup",
  "needs embedding setup",
  "warning",
  "writes data",
  "runtime mismatch",
  "needs attention",
  "requires reindex",
  "current",
  "next",
  "medium",
  "reindex needed",
  "restart needed",
]);

const DANGER_LABELS = new Set([
  "blocked",
  "failed",
  "error",
  "destructive",
  "danger",
  "degraded",
  "high",
]);

const INFO_LABELS = new Set([
  "optional",
  "manual submit",
  "info",
  "low",
  "new",
  "scanned",
  "needs model selection",
  "manual",
  "preference",
  "instructions only",
  "per request override",
  "per-request override",
  "default runtime",
  "informational",
  "advisory",
  "plan only",
  "catalog",
  "custom",
]);

const NEUTRAL_LABELS = new Set(["read-only", "readonly", "neutral"]);

export function getStatusTone(statusOrLabel: string): StatusTone {
  const label = normalizeStatusLabel(statusOrLabel);

  if (SUCCESS_LABELS.has(label)) {
    return "success";
  }
  if (WARNING_LABELS.has(label)) {
    return "warning";
  }
  if (DANGER_LABELS.has(label)) {
    return "danger";
  }
  if (INFO_LABELS.has(label)) {
    return "info";
  }
  if (NEUTRAL_LABELS.has(label)) {
    return "neutral";
  }
  return "neutral";
}

export function formatStatusLabel(label: string): string {
  return label.replaceAll("_", " ");
}

function normalizeStatusLabel(label: string): string {
  return formatStatusLabel(label).trim().toLowerCase().replace(/\s+/g, " ");
}
