"""Identifier and Correlation ID Generation Utilities."""

import uuid


def generate_id(prefix: str = "") -> str:
    """Generate a standard prefixed UUIDv4 identifier."""
    raw_id = str(uuid.uuid4()).replace("-", "")
    if prefix:
        return f"{prefix}_{raw_id}"
    return raw_id


def generate_correlation_id() -> str:
    """Generate a standardized correlation ID for request tracing."""
    return f"corr_{uuid.uuid4().hex[:16]}"


def generate_token(entropy_bytes: int = 32) -> str:
    """Generate a cryptographically secure random hexadecimal token."""
    import secrets
    return secrets.token_hex(entropy_bytes)
