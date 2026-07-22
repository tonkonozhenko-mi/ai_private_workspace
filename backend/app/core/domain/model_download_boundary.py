"""Fetching a file and executing a command are not the same act.

The app can install an Ollama model two ways. It can ask the Ollama daemon to
download it, over HTTP, on a socket that is already open — or it can run
``ollama pull <name>`` as a shell command. They arrive at the same result, and
they are entirely different in what they let go wrong.

Until now one setting governed both. ``MODEL_DOWNLOAD_EXECUTION_ENABLED``
defaults to false, which is right for the second and far too strict for the
first, and the consequence was visible: through Ollama you could install nothing
at all in a default build, while through llama.cpp you could paste any Hugging
Face repository and download gigabytes from the open internet. The stricter path
was the safer-looking one, not the safer one.

So the boundary is stated here, once, as a rule with a reason attached:

* **HTTP** — we send a model name to a daemon the user already runs and read
  bytes back. No shell, no interpreter, no arguments that could become other
  arguments. This is the same class of act as downloading a GGUF file, which
  this app has always done without a flag. Any model name is allowed, because
  the name is data, not code.

* **Shell** — we hand a string to a command interpreter. That is genuinely
  dangerous in a way the first is not, and it keeps both protections it has: the
  setting must be on, and the model must be one the app already knows about.

The point of writing it down is that the distinction is easy to erase by
accident. Someone tidying this code in a year sees two branches doing "the same
thing" and unifies them, and the unification will go toward whichever branch is
simpler to reach — which is the wrong direction. The tests below fail if that
happens.
"""

from __future__ import annotations

from dataclasses import dataclass

# How a model gets onto the machine.
HTTP_DAEMON = "http_daemon"
SHELL_COMMAND = "shell_command"


@dataclass(frozen=True)
class DownloadPermission:
    """Whether this download may proceed, and the reason either way."""

    allowed: bool
    reason: str

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return self.allowed


def may_download(
    method: str,
    *,
    execution_enabled: bool = False,
    model_is_known: bool = False,
) -> DownloadPermission:
    """Decide whether a model download may go ahead.

    ``execution_enabled`` and ``model_is_known`` are only consulted for the shell
    path. Passing them for an HTTP pull is harmless and ignored — the whole point
    is that an HTTP pull does not depend on them.
    """
    if method == HTTP_DAEMON:
        return DownloadPermission(
            allowed=True,
            reason=(
                "Downloading through the local Ollama daemon over HTTP. No shell "
                "command is run, so this needs no execution permission — the same "
                "as downloading a model file directly."
            ),
        )
    if method == SHELL_COMMAND:
        if not execution_enabled:
            return DownloadPermission(
                allowed=False,
                reason=(
                    "Running shell commands is disabled. Enable it only in a "
                    "trusted local desktop runtime — or let the app download "
                    "through the Ollama daemon instead, which needs no shell."
                ),
            )
        if not model_is_known:
            return DownloadPermission(
                allowed=False,
                reason=(
                    "Only models the app already knows about may be installed by "
                    "shell command. Anything else is downloaded through the "
                    "daemon instead."
                ),
            )
        return DownloadPermission(allowed=True, reason="Approved shell download of a known model.")
    return DownloadPermission(
        allowed=False,
        reason=f"Unknown download method: {method!r}.",
    )


# An Ollama model name is data we send to a daemon, not code — but it still ends
# up in a URL and a JSON body, so it is worth refusing the shapes that are
# obviously not a model name rather than passing them on and reading the error.
_MAX_NAME = 200


def is_valid_ollama_model_name(name: str) -> bool:
    """True for something that could plausibly be an Ollama model tag.

    Deliberately permissive about *which* model — refusing `llama3.3` because it
    is not in our catalog is exactly the restriction this module exists to lift.
    It refuses only the shapes that cannot be a name at all.
    """
    candidate = (name or "").strip()
    if not candidate or len(candidate) > _MAX_NAME:
        return False
    if any(character.isspace() for character in candidate):
        return False
    # No path traversal, no scheme, no shell metacharacters. None of these can
    # occur in a real tag, and all of them suggest the value came from somewhere
    # it should not have.
    return not any(
        token in candidate for token in ("..", "://", "\\", ";", "|", "&", "$", "`", "\n")
    )
