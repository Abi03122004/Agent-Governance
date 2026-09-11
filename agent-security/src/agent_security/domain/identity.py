"""Identity, Multi-Tenant Hierarchy, and Session Models."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Tenant(BaseModel):
    """Top-level isolation boundary."""
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    name: str = Field(..., min_length=1, max_length=128)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Project(BaseModel):
    """Logical sub-environment within a tenant."""
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    tenant_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentIdentity(BaseModel):
    """Authenticated agent identity."""
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    tenant_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    role: str = Field(default="standard_agent", min_length=1, max_length=64)
    is_active: bool = True
    is_suspended: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentSession(BaseModel):
    """Active conversational or operational session bounded by time and context."""
    session_id: str = Field(..., min_length=3, max_length=128)
    tenant_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    agent_id: str = Field(..., min_length=3, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    is_revoked: bool = False

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, v: datetime, values) -> datetime:
        return v

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        """Check if session is active, unrevoked, and not expired."""
        if self.is_revoked:
            return False
        current = now or datetime.now(timezone.utc)
        return current < self.expires_at
