"""Deterministic Canonical JSON and Cryptographic SHA-256 Hashing."""

import hashlib
import json
from typing import Any, Dict
from agent_security.domain.tool import ActionRequest


def canonical_json_bytes(data: Any) -> bytes:
    """Serialize data into deterministic, sorted canonical JSON bytes (RFC 8785 style)."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_action_canonical_payload(action: ActionRequest) -> Dict[str, Any]:
    """Extract canonical fields from an ActionRequest for hashing."""
    return {
        "organization_id": action.organization_id,
        "project_id": action.project_id,
        "agent_id": action.agent_id,
        "session_id": action.session_id,
        "task_id": action.task_id,
        "tool_name": action.tool_name,
        "arguments": action.arguments,
    }


def compute_action_canonical_hash(action: ActionRequest) -> str:
    """Compute the SHA-256 hexadecimal digest of the canonical action payload."""
    payload = compute_action_canonical_payload(action)
    serialized = canonical_json_bytes(payload)
    return hashlib.sha256(serialized).hexdigest()


def verify_action_hash(action: ActionRequest, expected_hash: str) -> bool:
    """Verify that an action matches an expected canonical hash."""
    computed = compute_action_canonical_hash(action)
    return computed.lower() == expected_hash.lower()


def compute_sha256_digest(data: Any) -> str:
    """General purpose SHA-256 digest of arbitrary serializable data."""
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(data).hexdigest()
    if isinstance(data, str):
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()
