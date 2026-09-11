"""Unit Tests for Structured JSON Logging and Secret Redaction in Logs."""

import json
import logging
from agent_security.core.redaction import REDACTION_MASK
from agent_security.logging import (
    StructuredJsonFormatter,
    request_id_ctx,
    trace_id_ctx,
)


def test_structured_json_formatter_formats_correctly():
    """Verify log record converts to JSON with timestamp, level, and service name."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Service initialized successfully.",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Service initialized successfully."
    assert parsed["service"] == "agent-governance-platform"
    assert "timestamp" in parsed


def test_structured_json_formatter_redacts_credentials():
    """Verify secrets inside log message text are redacted."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="auth_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=20,
        msg="Inbound call with Authorization: Bearer eyJhbGciOiJIUzI1Ni.sensitive.token",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert "eyJhbGciOiJIUzI1Ni" not in parsed["message"]
    assert REDACTION_MASK in parsed["message"]


def test_structured_json_formatter_injects_correlation_context():
    """Verify active request and trace IDs are injected into log JSON."""
    formatter = StructuredJsonFormatter()
    token_req = request_id_ctx.set("req_test_abc123")
    token_trc = trace_id_ctx.set("trc_test_xyz789")

    try:
        record = logging.LogRecord(
            name="context_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=30,
            msg="Resource threshold reached.",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["request_id"] == "req_test_abc123"
        assert parsed["trace_id"] == "trc_test_xyz789"
    finally:
        request_id_ctx.reset(token_req)
        trace_id_ctx.reset(token_trc)
