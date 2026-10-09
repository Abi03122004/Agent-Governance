"""Decision and Evaluation Domain Models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_security.domain.enums import PolicyDecision, RiskLevel
from agent_security.domain.approval import ApprovalTicket


class EvaluationDecision(BaseModel):
    """The normalized verdict returned by policy evaluation."""
    decision: PolicyDecision
    reason_code: str
    reasons: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    execution_authorization: Optional[str] = None
    approval_ticket_id: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionRecord(BaseModel):
    """Persisted decision audit trail metadata."""
    decision_id: str
    action_id: str
    canonical_action_hash: str
    decision: PolicyDecision
    reason_code: str
    evaluator: str = "deterministic_rule_engine"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
