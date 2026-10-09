"""Backward-compatibility re-exports for canonical hashing."""

from agent_security.core.hashing import (
    canonical_json_bytes,
    compute_action_canonical_payload,
    compute_action_canonical_hash,
    verify_action_hash,
)

__all__ = [
    "canonical_json_bytes",
    "compute_action_canonical_payload",
    "compute_action_canonical_hash",
    "verify_action_hash",
]
