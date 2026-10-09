"""Authentication and Credential Services."""

import hashlib
import secrets
from typing import Tuple


def generate_agent_credential() -> Tuple[str, str]:
    """
    Generate a new agent credential.
    Returns (plaintext_secret, hashed_secret).
    The plaintext_secret must only be shown once to the client.
    """
    # Generate a high-entropy secret using URL-safe characters
    plaintext_secret = f"agt_{secrets.token_urlsafe(32)}"
    
    # Hash the secret using SHA-256 (in production, use bcrypt or Argon2)
    # Using SHA-256 for Phase 2 simplicity as allowed by requirements.
    hashed_secret = hash_secret(plaintext_secret)
    return plaintext_secret, hashed_secret


def hash_secret(secret: str) -> str:
    """Hash a secret string."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(plain_secret: str, hashed_secret: str) -> bool:
    """Verify a plain secret against its hash."""
    return hash_secret(plain_secret) == hashed_secret
