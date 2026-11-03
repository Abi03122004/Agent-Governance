"""Execution Broker and Safe Execution Verification."""

from typing import Any, Dict


def execute_safe_action(
    decision: str,
    normalized: Dict[str, Any],
    action_id: str,
) -> Dict[str, Any]:
    """Execute permitted action with zero side effect."""
    if decision != "ALLOW":
        raise ValueError("Only ALLOWED actions are permitted to execute.")
    return {
        "message": "governed tool executed successfully",
        "tool": normalized.get("tool", "unknown"),
        "operation": normalized.get("operation", "execute"),
        "resource": normalized.get("resource", "default"),
        "action_id": action_id,
    }
