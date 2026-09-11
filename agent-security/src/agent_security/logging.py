"""Structured JSON Logging with Zero-Credential Redaction and Contextvars."""

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from agent_security.core.redaction import redact_sensitive_payload, redact_string

# Context variables for tracing request execution across async tasks
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


class StructuredJsonFormatter(logging.Formatter):
    """JSON log formatter that scrubs credentials and includes request/trace IDs."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_string(record.getMessage()),
            "service": "agent-governance-platform",
        }

        # Inject correlation context if active
        req_id = request_id_ctx.get()
        if req_id:
            log_payload["request_id"] = req_id

        trc_id = trace_id_ctx.get()
        if trc_id:
            log_payload["trace_id"] = trc_id

        # Include structured extra attributes if present
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_payload["details"] = redact_sensitive_payload(record.extra_fields)

        # Include exception details if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger to output structured JSON."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""
    return logging.getLogger(name)
