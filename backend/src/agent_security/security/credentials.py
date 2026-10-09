"""Cryptographic Credential Generation and Hashing."""

import hashlib
import secrets
from typing import Tuple


def generate_agent_credential() -> Tuple[str, str]:
    """Generate a high-entropy agent bearer secret and its SHA-256 hash.
    
    Returns (plaintext_secret, hashed_secret).
    """
    plaintext_secret = f"agt_{secrets.token_urlsafe(32)}"
    hashed_secret = hash_secret(plaintext_secret)
    return plaintext_secret, hashed_secret


def hash_secret(secret: str) -> str:
    """Hash a secret string using SHA-256."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(plain_secret: str, hashed_secret: str) -> bool:
    """Verify a plain secret against its stored hash."""
    return hash_secret(plain_secret) == hashed_secret
