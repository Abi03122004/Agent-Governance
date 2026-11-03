"""Cryptographic Provider Credential Vault with Authenticated AES-256-GCM Encryption."""

import base64
import os
import secrets
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from agent_security.config import get_settings


def _derive_vault_key(salt: bytes = b"agent_governance_provider_vault_salt_v1") -> bytes:
    """Derive a deterministic 256-bit (32-byte) AES key using HKDF-SHA256 from environment secret."""
    settings = get_settings()
    master_secret = os.environ.get("PROVIDER_VAULT_ENCRYPTION_KEY") or settings.SECRET_KEY
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"agent_provider_credential_vault_aes_256_gcm",
    )
    return hkdf.derive(master_secret.encode("utf-8"))


def encrypt_provider_credential(plaintext_api_key: str, key_version: int = 1) -> str:
    """Encrypt a provider API key using AES-256-GCM with a fresh random 96-bit nonce.
    
    Returns an envelope string: "v{key_version}.{nonce_b64}.{ciphertext_and_tag_b64}"
    """
    if not plaintext_api_key or not isinstance(plaintext_api_key, str):
        raise ValueError("Plaintext API key must be a non-empty string")
    
    key = _derive_vault_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)  # 96-bit nonce recommended for AES-GCM
    data = plaintext_api_key.encode("utf-8")
    
    # AESGCM.encrypt appends the 16-byte authentication tag to the ciphertext
    ciphertext = aesgcm.encrypt(nonce, data, associated_data=f"v{key_version}".encode("utf-8"))
    
    nonce_b64 = base64.urlsafe_b64encode(nonce).decode("utf-8").rstrip("=")
    ciphertext_b64 = base64.urlsafe_b64encode(ciphertext).decode("utf-8").rstrip("=")
    
    return f"v{key_version}.{nonce_b64}.{ciphertext_b64}"


def decrypt_provider_credential(encrypted_envelope: str) -> str:
    """Decrypt an encrypted envelope using AES-256-GCM.
    
    Verifies authenticity tag; raises ValueError on tampering or invalid key.
    """
    if not encrypted_envelope or "." not in encrypted_envelope:
        raise ValueError("Invalid encrypted credential format")
    
    parts = encrypted_envelope.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Malformed encrypted envelope: expected 3 parts")
    
    version_str, nonce_b64, ciphertext_b64 = parts
    try:
        # Restore base64 padding
        nonce_padding = "=" * (-len(nonce_b64) % 4)
        ciphertext_padding = "=" * (-len(ciphertext_b64) % 4)
        
        nonce = base64.urlsafe_b64decode(nonce_b64 + nonce_padding)
        ciphertext = base64.urlsafe_b64decode(ciphertext_b64 + ciphertext_padding)
    except Exception as exc:
        raise ValueError("Base64 decoding failed for encrypted credential") from exc
    
    key = _derive_vault_key()
    aesgcm = AESGCM(key)
    
    try:
        plaintext_bytes = aesgcm.decrypt(
            nonce,
            ciphertext,
            associated_data=version_str.encode("utf-8")
        )
        return plaintext_bytes.decode("utf-8")
    except Exception as exc:
        raise ValueError("Decryption failed: cryptographic authentication tag mismatch or corrupted ciphertext") from exc


def compute_key_fingerprint(api_key: str) -> str:
    """Compute a safe masked fingerprint for display without leaking secret material.
    
    Examples:
      'sk-proj-abc123456789xyz' -> 'sk-...9xyz'
      'shortkey' -> 'sh...ey'
    """
    clean_key = api_key.strip()
    if len(clean_key) <= 8:
        return f"{clean_key[:2]}...{clean_key[-2:]}" if len(clean_key) >= 4 else "****"
    
    if clean_key.startswith("sk-"):
        prefix = clean_key[:7] if len(clean_key) >= 12 else "sk-"
        suffix = clean_key[-4:]
        return f"{prefix}...{suffix}"
    
    return f"{clean_key[:4]}...{clean_key[-4:]}"

