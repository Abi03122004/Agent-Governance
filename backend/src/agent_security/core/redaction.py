"""Zero-Credential and Sensitive Data Redaction Engine."""

import re
from typing import Any, Dict, List, Set, Union

REDACTION_MASK = "[REDACTED_SECRET]"

SENSITIVE_KEY_PATTERNS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "private_key",
    "access_token",
    "refresh_token",
    "id_token",
    "session_token",
    "client_secret",
    "credit_card",
    "ssn",
}

# Regex for common secret patterns
SECRET_REGEXES = [
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
]


def redact_string(value: str) -> str:
    """Scan and redact well-known secret patterns in string values."""
    sanitized = value
    for pattern in SECRET_REGEXES:
        sanitized = pattern.sub(REDACTION_MASK, sanitized)
    return sanitized


def redact_sensitive_payload(data: Any) -> Any:
    """Recursively scrub sensitive keys and credential patterns from dictionaries and lists."""
    if isinstance(data, dict):
        sanitized_dict: Dict[str, Any] = {}
        for k, v in data.items():
            key_lower = str(k).lower().replace("-", "_")
            if any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS):
                sanitized_dict[k] = REDACTION_MASK
            else:
                sanitized_dict[k] = redact_sensitive_payload(v)
        return sanitized_dict
    elif isinstance(data, list):
        return [redact_sensitive_payload(item) for item in data]
    elif isinstance(data, str):
        return redact_string(data)
    return data


# Standard alias
redact_sensitive_data = redact_sensitive_payload
