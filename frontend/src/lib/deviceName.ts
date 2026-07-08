// A user-facing noun for the machine the app runs on. The app is cross-platform
// (macOS + Windows), so copy shouldn't hardcode "Mac". On macOS we keep the warm
// "Mac"; everywhere else we say the neutral, always-correct "computer".
//
// Detection is best-effort from the browser/webview platform string; when it
// can't be determined we fall back to "computer", which is never wrong.
export function deviceNoun(): string {
  if (typeof navigator !== "undefined") {
    const platform = (navigator.platform || navigator.userAgent || "").toLowerCase();
    if (platform.includes("mac")) {
      return "Mac";
    }
  }
  return "computer";
}
