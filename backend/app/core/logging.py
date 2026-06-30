"""
PATHS Backend — Logging configuration.

Sets up structured JSON logging in production and human-readable logs
in development. Each log record includes a correlation ID injected by
the HTTP middleware so cross-service traces are easy to link.

PATHS-177 (Phase 8 — Launch Hardening)
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar

from app.core.config import get_settings

# Per-request correlation ID — set by the HTTP middleware
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": get_correlation_id() or None,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include any extra kwargs passed to the logger call
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            } and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Configure root and application loggers."""
    settings = get_settings()
    level = logging.DEBUG if settings.debug else logging.INFO

    if settings.app_env == "development":
        # Human-readable for local development
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    else:
        # Structured JSON for production log aggregation
        formatter = JsonFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called multiple times
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
