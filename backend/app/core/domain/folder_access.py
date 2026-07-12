"""When the operating system, not the project, is the problem.

On macOS the first read of a folder under Documents/Desktop/Downloads triggers a TCC
prompt. Until the person answers it, the very first `listdir` simply *blocks* — no
error, no timeout. If the dialog is hidden behind a notification, the scan sits there
forever and the app cheerfully spins "Enumerating files…". Ten files, seven minutes,
no explanation. That is the worst kind of failure: the app looks broken, and the fix
is one click the person never saw.

If they deny it (or the grant is later revoked), we get an EACCES/EPERM instead —
and today `os.walk` swallows it, so the scan "succeeds" with a silently smaller file
set. A quietly incomplete index is worse than an honest error.

One sentence, in one place, used by the scan, the index and anything else that reads
the folder — and mirrored in the frontend (see `lib/folderAccess.ts`). It names the
cause and the exact place to fix it, because "permission denied" helps nobody.
"""

from __future__ import annotations

import errno

FOLDER_PERMISSION_MESSAGE = (
    "This app doesn't have permission to read that folder. macOS may be asking for "
    "access right now — look for a system dialog. You can also grant it in System "
    "Settings → Privacy & Security → Files and Folders."
)


class FolderPermissionError(PermissionError):
    """The folder exists, but the OS will not let us read it.

    Carries the user-facing sentence as its message, so every layer above — the job
    runner, the API, the UI — can show it without re-deriving it from an errno.
    """

    def __init__(self, path: str) -> None:
        super().__init__(FOLDER_PERMISSION_MESSAGE)
        self.path = path


def is_permission_error(error: OSError) -> bool:
    """EACCES/EPERM, however the platform spells it today."""
    return isinstance(error, PermissionError) or error.errno in (errno.EACCES, errno.EPERM)
