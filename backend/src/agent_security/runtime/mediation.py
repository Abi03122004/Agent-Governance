"""Pre-Execution Action Normalization and Mediation Lifecycle."""

import hashlib
import json
from typing import Any, Dict

from agent_security.security.context import AuthenticatedAgent
from agent_security.domain.runtime import RuntimeActionInput


def normalize_action(
    identity: AuthenticatedAgent,
    request: RuntimeActionInput,
) -> Dict[str, Any]:
    """Derive canonical action representation from authenticated credentials."""
    return {
        "agent_id": identity.agent_id,
        "arguments": request.arguments,
        "destination": (request.destination or "").strip().lower() or None,
        "operation": request.operation.strip().lower().replace(" ", "_"),
        "organization_id": identity.organization_id,
        "project_id": identity.project_id,
        "resource": request.resource.strip().lower(),
        "session_id": request.session_id,
        "tool": request.tool.strip().lower().replace(" ", "_"),
    }


def compute_action_digest(normalized: Dict[str, Any]) -> str:
    """Generate canonical SHA-256 digest string for normalized action."""
    payload = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
