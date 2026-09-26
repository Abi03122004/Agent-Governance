"""Tamper-Evident Audit Event Schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from agent_security.domain.enums import AuditSeverity, ExecutionState, PolicyDecision


class AuditEvent(BaseModel):
    """Structured, tamper-evident audit record capturing action lifecycle and security decisions."""
    event_id: str = Field(..., min_length=8, max_length=128)
    organization_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    agent_id: str = Field(..., min_length=3, max_length=64)
    session_id: str = Field(..., min_length=8, max_length=128)
    task_id: str = Field(..., min_length=1, max_length=128)
    action_id: str = Field(..., min_length=8, max_length=128)
    tool_name: str = Field(..., min_length=1, max_length=64)
    canonical_action_hash: str = Field(..., min_length=64, max_length=64)
    policy_decision: PolicyDecision
    execution_state: ExecutionState
    severity: AuditSeverity = AuditSeverity.INFO
    event_type: str = Field(..., min_length=1, max_length=64)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)
    previous_event_hash: Optional[str] = None
    event_hash: Optional[str] = None
