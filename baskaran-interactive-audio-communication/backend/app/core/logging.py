"""
Structured logging configuration.
Outputs JSON lines in production, pretty-formatted in debug mode.
"""

import logging
import sys
from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
        if settings.debug
        else '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","line":%(lineno)d,"msg":"%(message)s"}'
    )

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format=fmt,
        stream=sys.stdout,
    )

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
