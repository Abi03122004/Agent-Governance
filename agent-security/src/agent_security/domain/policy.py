"""Declarative Policy and Governance Rule Models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from agent_security.domain.enums import PolicyDecision
from agent_security.domain.identity import AgentIdentity, AgentSession
from agent_security.domain.tool import ActionRequest, ToolDefinition


class PolicyRule(BaseModel):
    """An individual deterministic governance rule."""
    rule_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    decision: PolicyDecision
    target_tool: str = Field(default="*", description="Tool name or '*' for all tools")
    condition_expr: Optional[str] = None
    priority: int = Field(default=100, description="Lower number = higher priority")
    is_active: bool = True


class Policy(BaseModel):
    """A collection of governance rules scoped to a tenant or project."""
    policy_id: str = Field(..., min_length=3, max_length=64)
    tenant_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    version: int = Field(default=1, ge=1)
    rules: List[PolicyRule] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEvaluationContext(BaseModel):
    """Runtime evaluation context passed into the policy engine."""
    action: ActionRequest
    session: AgentSession
    agent: AgentIdentity
    tool: ToolDefinition
    ai_risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ai_risk_reason: Optional[str] = None
