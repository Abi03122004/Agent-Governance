"""Deterministic Canonical JSON and Cryptographic Hashing."""

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
    """Extract canonical fields from an ActionRequest for hashing.
    
    Excludes ephemeral or runtime fields that do not define the semantic action,
    ensuring that exact arguments, target tool, session, tenant, and identity are locked.
    """
    return {
        "tenant_id": action.tenant_id,
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
