"""Core Domain Enums and Status Dimensions."""

from enum import Enum


class PolicyDecision(str, Enum):
    """The four explicit governance verdicts rendered by the policy engine."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    SUSPEND = "SUSPEND"


class ExecutionState(str, Enum):
    """Execution lifecycle states managed by the Execution Broker."""
    SUBMITTED = "SUBMITTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SCHEDULED = "SCHEDULED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, Enum):
    """Lifecycle states of a cryptographic human-in-the-loop approval ticket."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


class RiskLevel(str, Enum):
    """Heuristic and AI classifier risk severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuditSeverity(str, Enum):
    """Severity classification for tamper-evident audit events."""
    INFO = "INFO"
    WARNING = "WARNING"
    SECURITY_ALERT = "SECURITY_ALERT"
    CRITICAL = "CRITICAL"
