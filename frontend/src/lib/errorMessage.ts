/** Turn an unknown thrown value into a short, user-facing message.
 *
 * Most errors reach here from the API client: `assertOk` throws either the
 * backend's `detail` string (already human-readable) or a bare
 * "<status> <statusText>" fallback, and `fetch` itself throws when the local
 * backend isn't reachable. Raw "Failed to fetch" or "500 Internal Server Error"
 * is confusing, so map the common technical cases to actionable sentences and
 * otherwise return the original message unchanged.
 */
export function errorMessage(error: unknown): string {
  const text = (error instanceof Error ? error.message : "").trim();
  const lower = text.toLowerCase();

  // The local backend is unreachable — not started yet, crashed, or wrong port.
  if (
    text === "" ||
    lower.includes("failed to fetch") ||
    lower.includes("load failed") ||
    lower.includes("networkerror") ||
    lower.includes("fetch failed") ||
    lower.includes("err_connection") ||
    lower.includes("connection refused")
  ) {
    return "Can't reach the local AI engine. Make sure it's running (open Settings to start it), then try again.";
  }

  if (lower.includes("aborted")) {
    return "The request was cancelled.";
  }
  if (lower.includes("timed out") || lower.includes("timeout")) {
    return "That took too long and timed out. Try again — a large project or a cold model can be slow the first time.";
  }

  // The "<status> <statusText>" fallback shape from assertOk (3 digits + space),
  // e.g. "500 Internal Server Error". Anchored so a detail like "500 files" that
  // happens to start with a number isn't mistaken for an HTTP status.
  const statusMatch = text.match(/^(\d{3})\s/);
  if (statusMatch) {
    const status = Number(statusMatch[1]);
    if (status === 503) {
      return "The local engine is still starting. Give it a few seconds and try again.";
    }
    if (status === 404) {
      return "That wasn't found on the local server — it may have been removed.";
    }
    if (status === 429) {
      return "Too many requests at once. Wait a moment and try again.";
    }
    if (status >= 500) {
      return "Something went wrong on the local server. Try again; if it keeps happening, restart the app.";
    }
  }

  // Otherwise it's a backend `detail` string, which is already readable.
  return text;
}
