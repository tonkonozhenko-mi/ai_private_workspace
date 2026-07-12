/** The one sentence we say when the operating system, not the project, is in the way.
 *
 * On macOS the first read of a folder under Documents triggers a permission dialog,
 * and until it is answered the read simply *blocks* — no error, no timeout. If the
 * dialog is hidden behind a notification, the app spins "Enumerating files…" forever.
 * Ten files, seven minutes, no explanation. The fix is one click the person never saw,
 * so the app's job is to point at it.
 *
 * Kept here, not inline in a component, because the scan is not the only thing that
 * reads the folder: indexing, Ask and the Investigator hit the same wall if the grant
 * is revoked on a live workspace. Must stay in step with the backend's
 * `core/domain/folder_access.py` — the backend sends this same sentence as the failure
 * message, and the watchdog below shows it before any failure arrives.
 */
export const FOLDER_PERMISSION_HINT =
  "macOS may be asking for permission to read this folder — look for a system dialog. " +
  "You can also grant access in System Settings → Privacy & Security → Files and Folders.";

/** How long a job may make no progress at all before we suspect the dialog.
 *
 * A healthy walk reports its running file count as it descends, so silence means
 * stuck, not slow. Five seconds is long enough not to cry wolf on a cold disk. */
export const NO_PROGRESS_HINT_AFTER_MS = 5000;
