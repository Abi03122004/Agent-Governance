"""Provider-neutral request and response contracts for the runtime gateway."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class RuntimeActionInput(BaseModel):
    """Untrusted action data supplied by an authenticated agent."""

    session_id: str = Field(min_length=3, max_length=128)
    tool: str = Field(min_length=1, max_length=64)
    operation: str = Field(min_length=1, max_length=64)
    resource: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict)
    destination: str | None = Field(default=None, max_length=512)
    purpose: str | None = Field(default=None, max_length=512)


class RuntimeDecision(BaseModel):
    action_id: str
    decision: Literal["ALLOW", "BLOCK", "REQUIRE_APPROVAL", "SUSPEND"]
    policy_id: str
    policy_version: int
    reason_code: str
    explanation: str
    risk_signals: list[str] = Field(default_factory=list)
    action_digest: str
    correlation_id: str
    execution_authorization: str | None = None
    execution_authorization_expires_at: datetime | None = None


class ExecuteActionRequest(BaseModel):
    execution_authorization: str = Field(min_length=20)


class ReportResultRequest(BaseModel):
    execution_authorization: str = Field(min_length=20)
    status: Literal["succeeded", "failed"]
    output: dict[str, Any] = Field(default_factory=dict)


class RuntimeActivity(BaseModel):
    action_id: str
    organization_id: str
    project_id: str
    agent_id: str
    session_id: str
    tool: str
    operation: str
    resource: str
    decision: str
    action_digest: str
    correlation_id: str
    timestamp: datetime
