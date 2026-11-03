"""Governance SDK Exception Hierarchy."""

from typing import Any, Dict, Optional


class GovernanceError(Exception):
    """Base exception for all governance errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GatewayConnectionError(GovernanceError):
    """Raised when the Governance Gateway is unreachable or timed out."""
    pass


class AuthenticationError(GovernanceError):
    """Raised when agent credentials are invalid, expired, or revoked (HTTP 401)."""
    pass


class TenantIsolationError(GovernanceError):
    """Raised when an agent attempts to access resources outside its tenant scope (HTTP 403)."""
    pass


class SessionExpiredError(GovernanceError):
    """Raised when the runtime session is expired or not active."""
    pass


class PolicyBlockedError(GovernanceError):
    """Raised when a tool action is strictly BLOCKED by policy."""
    def __init__(
        self,
        message: str,
        action_id: str,
        reason_code: str,
        explanation: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.action_id = action_id
        self.reason_code = reason_code
        self.explanation = explanation


class AgentSuspendedError(GovernanceError):
    """Raised when a tool action is rejected because the agent is SUSPENDED."""
    def __init__(
        self,
        message: str,
        action_id: Optional[str] = None,
        reason_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.action_id = action_id
        self.reason_code = reason_code


class ApprovalRequiredError(GovernanceError):
    """Raised when an action requires human approval before execution."""
    def __init__(
        self,
        message: str,
        action_id: str,
        ticket_id: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.action_id = action_id
        self.ticket_id = ticket_id


class ApprovalTimeoutError(GovernanceError):
    """Raised when waiting for human approval exceeds the timeout."""
    def __init__(self, ticket_id: str, timeout_seconds: float):
        super().__init__(
            f"Approval timed out after {timeout_seconds}s for ticket '{ticket_id}'",
            {"ticket_id": ticket_id, "timeout_seconds": timeout_seconds},
        )
        self.ticket_id = ticket_id
        self.timeout_seconds = timeout_seconds


class ApprovalRejectedError(GovernanceError):
    """Raised when a human approver explicitly rejects the requested action."""
    def __init__(self, ticket_id: str, reason: Optional[str] = None):
        super().__init__(
            f"Action rejected by human operator (ticket '{ticket_id}'): {reason or 'No reason provided'}",
            {"ticket_id": ticket_id, "reason": reason},
        )
        self.ticket_id = ticket_id
        self.reason = reason


class ExecutionAuthorizationError(GovernanceError):
    """Raised when an execution token is missing, expired, or already used."""
    pass


class ToolExecutionError(GovernanceError):
    """Raised when protected tool execution encounters an unhandled runtime error."""
    pass

