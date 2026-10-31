"""Structured logging configuration for Python Tutor."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def _log_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    path = Path(base) / "python-tutor" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging(level: int = logging.INFO, json_output: bool = False) -> None:
    """Configure application-wide logging.

    Args:
        level: Minimum log level (default INFO).
        json_output: If True, emit JSON lines to stdout (for container logs).
    """
    log_file = _log_dir() / "python-tutor.log"

    # File handler with rotation (5 MB, 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Formatters
    if json_output and HAS_STRUCTLOG:
        # structlog will handle JSON formatting
        formatter = logging.Formatter("%(message)s")
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("PyQt6").setLevel(logging.WARNING)

    if HAS_STRUCTLOG and json_output:
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


def get_logger(name: str):
    """Get a logger instance (structlog if available, else stdlib)."""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


# Convenience: configure on import if env var set
if os.environ.get("PYTHON_TUTOR_LOG_JSON"):
    configure_logging(json_output=True)
else:
    configure_logging()
