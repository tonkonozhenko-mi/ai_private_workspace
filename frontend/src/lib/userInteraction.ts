/**
 * Has the person touched the app yet?
 *
 * Checking a project for on-disk changes walks its folder, which makes macOS ask
 * for folder access. We only run those checks AFTER a deliberate interaction, so
 * the prompt is tied to something the person did — never to a silent cold launch
 * of an app that opens on login.
 *
 * It lives here because a group of repositories needs the same gate for the same
 * reason, and a second copy of a rule like this is a second thing to forget.
 */

let interacted = false;

if (typeof window !== "undefined") {
  const mark = () => {
    interacted = true;
    window.removeEventListener("pointerdown", mark);
    window.removeEventListener("keydown", mark);
  };
  window.addEventListener("pointerdown", mark);
  window.addEventListener("keydown", mark);
}

export function hasUserInteracted(): boolean {
  return interacted;
}
