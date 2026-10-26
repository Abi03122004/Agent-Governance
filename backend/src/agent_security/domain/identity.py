"""Identity, Multi-Organization Hierarchy, and Session Models."""

from datetime import datetime, timezone
from typing import Any, Optional, List
from pydantic import BaseModel, Field, field_validator


class Organization(BaseModel):
    """Top-level isolation boundary."""
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    name: str = Field(..., min_length=1, max_length=128)
    status: str = Field(default="active", pattern=r"^(active|suspended)$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        return self.status == "active"


Tenant = Organization


class Project(BaseModel):
    """Logical sub-environment within an organization."""
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    organization_id: Optional[str] = Field(default=None, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    status: str = Field(default="active", pattern=r"^(active|suspended|archived)$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def __init__(self, **data: Any):
        if "tenant_id" in data and "organization_id" not in data:
            data["organization_id"] = data.pop("tenant_id")
        super().__init__(**data)

    @property
    def tenant_id(self) -> str:
        return self.organization_id or ""


class User(BaseModel):
    """Human user for the control plane."""
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    email: str = Field(..., min_length=3, max_length=256)
    display_name: str = Field(..., min_length=1, max_length=128)
    status: str = Field(default="active", pattern=r"^(active|suspended)$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Membership(BaseModel):
    """User membership within an organization."""
    id: str = Field(..., min_length=3, max_length=64)
    user_id: str = Field(..., min_length=3, max_length=64)
    organization_id: str = Field(..., min_length=3, max_length=64)
    role: str = Field(..., pattern=r"^(administrator|security_operator|approver|viewer)$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentIdentity(BaseModel):
    """Authenticated agent identity."""
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    organization_id: Optional[str] = Field(default="", max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    owner: str = Field(default="system", min_length=1, max_length=128)
    environment: str = Field(default="development", min_length=1, max_length=64)
    purpose: Optional[str] = Field(None, max_length=512)
    status: str = Field(default="active", pattern=r"^(active|revoked|suspended)$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def __init__(self, **data: Any):
        if "tenant_id" in data and "organization_id" not in data:
            data["organization_id"] = data.pop("tenant_id")
        super().__init__(**data)

    @property
    def tenant_id(self) -> str:
        return self.organization_id or ""

    @property
    def is_suspended(self) -> bool:
        return self.status == "suspended"

    @is_suspended.setter
    def is_suspended(self, val: bool):
        self.status = "suspended" if val else "active"


class AgentCredential(BaseModel):
    """Agent credential metadata."""
    id: str = Field(..., min_length=3, max_length=64)
    agent_id: str = Field(..., min_length=3, max_length=64)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class AgentSession(BaseModel):
    """Active conversational or operational session bounded by time and context."""
    session_id: str = Field(..., min_length=3, max_length=128)
    organization_id: Optional[str] = Field(default="", max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    agent_id: str = Field(..., min_length=3, max_length=64)
    credential_id: Optional[str] = None
    status: str = Field(default="active", pattern=r"^(active|completed|terminated|revoked)$")
    correlation_id: Optional[str] = None
    is_revoked: bool = False
    expires_at: Optional[datetime] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None

    def __init__(self, **data: Any):
        if "tenant_id" in data and "organization_id" not in data:
            data["organization_id"] = data.pop("tenant_id")
        super().__init__(**data)

    @property
    def tenant_id(self) -> str:
        return self.organization_id or ""

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        """Check if session is active, unrevoked, and unexpired."""
        if self.is_revoked or self.status != "active":
            return False
        current = now or datetime.now(timezone.utc)
        if self.expires_at is not None and current >= self.expires_at:
            return False
        return True
