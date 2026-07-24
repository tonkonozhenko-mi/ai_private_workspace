// Turning a failed model switch into a message the user actually sees.
//
// The 0.7.6 blocker was a *silent* failure: the switch fell over and the screen
// said nothing. The rule now is that every switch failure ends as words on the
// screen. The backend already phrases the real reason ("Could not start X: …");
// this helper makes sure we surface that phrasing when we have it, and still say
// something useful when we don't — never an empty string, which would render as
// no error at all.

/** A non-empty, user-facing sentence for a failed answer/search-model switch.
 *  Prefers the backend's worded reason; falls back to a plain default. */
export function modelSwitchErrorMessage(
  error: unknown,
  kind: "answer" | "search" = "answer",
): string {
  const fallback =
    kind === "search"
      ? "Could not switch the search model."
      : "Could not switch the answer model.";
  if (error instanceof Error) {
    const message = error.message.trim();
    if (message) return message;
  }
  if (typeof error === "string" && error.trim()) return error.trim();
  return fallback;
}
