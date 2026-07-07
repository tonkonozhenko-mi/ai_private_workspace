"""The app logger gets a stdout handler so app.* logs actually surface, and the
setup is idempotent (no duplicate handlers) and doesn't bubble up to root."""

import io
import logging

from app.config.logging_setup import _HANDLER_MARKER, configure_app_logging


def _our_handlers():
    return [
        h for h in logging.getLogger("app").handlers if getattr(h, _HANDLER_MARKER, False)
    ]


def test_app_logger_emits_after_configuration():
    configure_app_logging()
    handlers = _our_handlers()
    assert len(handlers) == 1
    buffer = io.StringIO()
    handlers[0].stream = buffer
    logging.getLogger("app.core.use_cases.scan_project").info("scan.phases discover=1ms")
    assert "scan.phases discover=1ms" in buffer.getvalue()


def test_configuration_is_idempotent():
    configure_app_logging()
    configure_app_logging()
    configure_app_logging()
    # Still exactly one handler of ours — never a duplicate that double-prints.
    assert len(_our_handlers()) == 1


def test_app_logger_does_not_propagate_to_root():
    configure_app_logging()
    # propagate off, so lines aren't duplicated through the root logger.
    assert logging.getLogger("app").propagate is False
