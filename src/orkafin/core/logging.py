"""Structured, request-correlated logging with central redaction."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime

from orkafin.core.request_id import get_request_id

REDACTED_VALUE = "[REDACTED]"
SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "cookie",
        "token",
        "secret",
        "password",
        "api_key",
        "notes",
        "raw_content",
        "prompt",
        "model_input",
        "model_output",
    }
)
_STANDARD_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__)


def is_sensitive_key(key: str) -> bool:
    """Identify keys whose values must not be emitted to logs."""
    normalized_key = key.lower().replace("-", "_")
    return any(part in normalized_key for part in SENSITIVE_KEY_PARTS)


def redact_value(value: object) -> object:
    """Convert values to JSON-compatible structures without exposing secrets."""
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED_VALUE if is_sensitive_key(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


class RedactingFilter(logging.Filter):
    """Redact sensitive values before any handler formats a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in tuple(record.__dict__.items()):
            if key in _STANDARD_RECORD_KEYS:
                continue
            record.__dict__[key] = REDACTED_VALUE if is_sensitive_key(key) else redact_value(value)

        if isinstance(record.msg, Mapping):
            record.msg = json.dumps(redact_value(record.msg), sort_keys=True)
            record.args = ()
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Render logs as bounded JSON-compatible event records."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_KEYS and key != "request_id":
                payload[key] = REDACTED_VALUE if is_sensitive_key(key) else redact_value(value)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(log_level: str) -> logging.Logger:
    """Configure the application logger without writing unredacted records."""
    logger = logging.getLogger("orkafin")
    logger.setLevel(log_level)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return an OrkaFin child logger that inherits the redacted handler."""
    return logging.getLogger(f"orkafin.{name}")
