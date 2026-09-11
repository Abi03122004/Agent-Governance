"""Tool Definitions and Action Request Schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from agent_security.domain.enums import RiskLevel


class ToolParameter(BaseModel):
    """Schema descriptor for an individual tool parameter."""
    name: str = Field(..., min_length=1, max_length=64)
    type: str = Field(..., min_length=1, max_length=32)
    description: str = ""
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    """Registered capability exposed to agents via the Execution Broker."""
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    description: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)
    rate_limit_per_minute: int = 60
    cost_per_call: float = 0.0


class ActionRequest(BaseModel):
    """An invocation request submitted by an agent."""
    action_id: str = Field(..., min_length=3, max_length=128)
    tenant_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    agent_id: str = Field(..., min_length=3, max_length=64)
    session_id: str = Field(..., min_length=3, max_length=128)
    task_id: str = Field(..., min_length=1, max_length=128)
    tool_name: str = Field(..., min_length=1, max_length=64)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
