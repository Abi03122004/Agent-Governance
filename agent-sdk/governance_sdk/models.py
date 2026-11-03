"""Governance SDK Domain and Request/Response Models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActionDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    SUSPEND = "SUSPEND"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class AgentSession(BaseModel):
    session_id: str
    organization_id: str
    project_id: str
    agent_id: str
    status: str
    expires_at: Optional[datetime] = None


class RuntimeActionInput(BaseModel):
    session_id: str
    tool: str
    operation: str
    resource: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    destination: Optional[str] = None
    purpose: Optional[str] = None
    action_description: Optional[str] = None
    execution_context: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None
    agent_id: Optional[str] = None
    organization_id: Optional[str] = None


class EvaluationResult(BaseModel):
    action_id: str
    decision: ActionDecision
    policy_id: str
    policy_version: int
    reason_code: str
    explanation: str
    risk_signals: List[str] = Field(default_factory=list)
    action_digest: str
    correlation_id: str
    execution_authorization: Optional[str] = None
    execution_authorization_expires_at: Optional[datetime] = None
    approval_ticket_id: Optional[str] = None
    request_id: Optional[str] = None

    @property
    def is_allowed(self) -> bool:
        return self.decision == ActionDecision.ALLOW

    @property
    def is_blocked(self) -> bool:
        return self.decision == ActionDecision.BLOCK

    @property
    def requires_approval(self) -> bool:
        return self.decision == ActionDecision.REQUIRE_APPROVAL

    @property
    def is_suspended(self) -> bool:
        return self.decision == ActionDecision.SUSPEND


class ApprovalTicket(BaseModel):
    ticket_id: str
    status: str
    execution_authorization: Optional[str] = None


class ExecutionResult(BaseModel):
    action_id: str
    status: str
    result: Optional[Any] = None
    idempotent: bool = False

