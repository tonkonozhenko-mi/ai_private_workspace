// Synthetic source paths the backend indexes as pseudo-documents. They carry a
// namespaced path (so they never collide with a real file), but that raw token
// shouldn't leak into the UI — show a human label instead.
export const HANDBOOK_PSEUDO_PATH = "__project_handbook__";

/** A Map, not an object literal, so this answers only the question it was asked.
 *
 * As a plain object, `PSEUDO_LABELS[sourcePath]` also answers for every name
 * Object.prototype happens to carry: a file called `constructor` came back as
 * "function Object() { [native code] }", one called `__proto__` as an object
 * React refuses to render. `?? sourcePath` could not catch either, because
 * neither is null — the lookup had already answered, wrongly. A page named
 * "toString" is not a hypothetical in a wiki about JavaScript. */
const PSEUDO_LABELS = new Map<string, string>([[HANDBOOK_PSEUDO_PATH, "Project handbook"]]);

/** Display label for a retrieved source's path: a friendly name for synthetic
 *  pseudo-documents, otherwise the path unchanged. */
export function formatSourceLabel(sourcePath: string): string {
  return PSEUDO_LABELS.get(sourcePath) ?? sourcePath;
}
