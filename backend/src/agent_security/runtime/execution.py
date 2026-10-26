"""Execution Broker and Safe Execution Verification."""

from typing import Any, Dict


def execute_safe_action(
    decision: str,
    normalized: Dict[str, Any],
    action_id: str,
) -> Dict[str, Any]:
    """Execute permitted harmless action with zero side effect."""
    if decision != "ALLOW":
        raise ValueError("Only ALLOWED actions are permitted to execute.")
    if normalized.get("tool") not in {"safe_echo", "database", "file", "kubernetes"}:
        raise ValueError(f"Tool {normalized.get('tool')} is not authorized for demonstration execution.")
    return {
        "message": "safe tool executed",
        "tool": normalized["tool"],
        "operation": normalized["operation"],
        "resource": normalized["resource"],
        "action_id": action_id,
    }
