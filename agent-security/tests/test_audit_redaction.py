"""Unit Tests for Zero-Credential Logging and Sensitive Payload Redaction."""

from agent_security.core.redaction import (
    REDACTION_MASK,
    redact_sensitive_payload,
    redact_string,
)


def test_redact_sensitive_keys_in_dict():
    raw_payload = {
        "user_id": "usr-123",
        "action": "query_records",
        "api_key": "live_key_abcdef123456",
        "database_password": "super_secret_db_pass",
        "nested": {
            "auth_token": "jwt_token_here",
            "safe_field": "visible_data",
        },
    }

    sanitized = redact_sensitive_payload(raw_payload)

    assert sanitized["user_id"] == "usr-123"
    assert sanitized["api_key"] == REDACTION_MASK
    assert sanitized["database_password"] == REDACTION_MASK
    assert sanitized["nested"]["auth_token"] == REDACTION_MASK
    assert sanitized["nested"]["safe_field"] == "visible_data"


def test_redact_string_patterns():
    log_line = "Agent transmitted Authorization: Bearer eyJhbGciOiJIUzI1Ni... to endpoint"
    sanitized = redact_string(log_line)
    assert "Bearer" not in sanitized or REDACTION_MASK in sanitized
    assert "eyJhbGciOiJIUzI1Ni" not in sanitized


def test_redact_api_key_patterns():
    log_line = "Using client key sk-ant-api03-abcdef123456789012345678"
    sanitized = redact_string(log_line)
    assert "sk-ant-api03" not in sanitized
    assert REDACTION_MASK in sanitized
