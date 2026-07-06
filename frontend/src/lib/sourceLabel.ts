// Synthetic source paths the backend indexes as pseudo-documents. They carry a
// namespaced path (so they never collide with a real file), but that raw token
// shouldn't leak into the UI — show a human label instead.
export const HANDBOOK_PSEUDO_PATH = "__project_handbook__";

const PSEUDO_LABELS: Record<string, string> = {
  [HANDBOOK_PSEUDO_PATH]: "Project handbook",
};

/** Display label for a retrieved source's path: a friendly name for synthetic
 *  pseudo-documents, otherwise the path unchanged. */
export function formatSourceLabel(sourcePath: string): string {
  return PSEUDO_LABELS[sourcePath] ?? sourcePath;
}
