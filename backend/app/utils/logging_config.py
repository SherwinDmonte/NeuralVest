"""Logging setup: one format for the whole app, request IDs on every line, secrets masked."""

import logging
import re
from contextvars import ContextVar

# Holds the ID of the HTTP request currently being handled (set by RequestIdMiddleware).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# mongodb://user:password@host  or  mongodb+srv://user:password@host
_MONGO_CREDENTIALS = re.compile(r"(mongodb(?:\+srv)?://)([^:@/\s]+):([^@/\s]+)@")
# key=value pairs whose key looks secret (password=..., secret=..., token=...)
_SECRET_PAIRS = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)(\s*[=:]\s*)([^\s,;&]+)")


def redact(text: str) -> str:
    """Mask credentials that could otherwise end up in log files."""
    text = _MONGO_CREDENTIALS.sub(r"\1\2:***@", text)
    return _SECRET_PAIRS.sub(r"\1\2***", text)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # PyMongo's own debug output is very noisy and can include server details.
    logging.getLogger("pymongo").setLevel(logging.WARNING)
