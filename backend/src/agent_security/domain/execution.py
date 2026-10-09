"""Execution Record Decoupled from Policy Decision."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from agent_security.domain.enums import ExecutionState, PolicyDecision


class ExecutionRecord(BaseModel):
    """Runtime tracking record maintaining independent Policy Decision and Execution States."""
    execution_id: str = Field(..., min_length=8, max_length=128)
    action_id: str = Field(..., min_length=8, max_length=128)
    canonical_action_hash: str = Field(..., min_length=64, max_length=64)
    policy_decision: PolicyDecision
    execution_state: ExecutionState = Field(default=ExecutionState.SUBMITTED)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approval_ticket_id: Optional[str] = None
    sanitized_output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
