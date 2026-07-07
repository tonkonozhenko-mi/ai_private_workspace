"""Make the application's own logs actually surface.

Uvicorn configures logging handlers only for its own loggers (``uvicorn`` /
``uvicorn.access`` / ``uvicorn.error``). Every ``logging.getLogger("app.…")``
message therefore had no handler and was silently dropped — which is why, for
example, the scan phase-timing lines never appeared in ``backend.log`` even though
the code emitted them.

We attach a single stdout handler to the top-level ``app`` logger (not the root
logger), so it survives uvicorn's own ``dictConfig`` regardless of import/startup
ordering — uvicorn's config never names ``app`` and runs with
``disable_existing_loggers=False``, so our handler is left intact. ``propagate`` is
turned off so messages aren't duplicated through the root logger.
"""

import logging
import os
import sys

# Marker on handlers we add, so re-configuration stays idempotent (no duplicate
# lines if this is called more than once, e.g. under a reloader).
_HANDLER_MARKER = "_ai_workspace_app_handler"


def configure_app_logging() -> None:
    """Attach a stdout handler to the ``app`` logger at the configured level.

    Level comes from ``AI_WORKSPACE_LOG_LEVEL`` (default ``INFO``). Idempotent.
    """
    level_name = os.environ.get("AI_WORKSPACE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)

    already_configured = any(
        getattr(handler, _HANDLER_MARKER, False) for handler in app_logger.handlers
    )
    if not already_configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
        setattr(handler, _HANDLER_MARKER, True)
        app_logger.addHandler(handler)

    # Don't also bubble up to the root logger (which uvicorn may or may not have a
    # handler on) — that would double-print every app log line.
    app_logger.propagate = False
