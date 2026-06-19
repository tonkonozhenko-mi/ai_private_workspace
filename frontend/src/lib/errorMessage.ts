/** Turn an unknown thrown value into a user-facing message string. */
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected request error";
}
