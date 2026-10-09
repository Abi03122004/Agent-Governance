"""Core Pydantic Request and Response Schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field

from agent_security.domain.enums import PolicyDecision, RiskLevel, ExecutionState


class OrganizationCreateRequest(BaseModel):
    id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=2, max_length=128)


class ProjectCreateRequest(BaseModel):
    id: str = Field(..., min_length=3, max_length=64)
    organization_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=2, max_length=128)


class UserCreateRequest(BaseModel):
    id: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    display_name: str = Field(..., min_length=2, max_length=128)


class MembershipCreateRequest(BaseModel):
    id: str = Field(..., min_length=3, max_length=64)
    user_id: str = Field(..., min_length=3, max_length=64)
    organization_id: str = Field(..., min_length=3, max_length=64)
    role: str = Field(default="administrator", min_length=3, max_length=64)


class AgentCreateRequest(BaseModel):
    id: str = Field(..., min_length=3, max_length=64)
    organization_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=2, max_length=128)
    owner: str = Field(..., min_length=2, max_length=128)
    environment: str = Field(default="development", max_length=64)
    purpose: Optional[str] = None


class CredentialCreateResponse(BaseModel):
    credential_id: str
    token: str
    expires_at: Optional[datetime] = None


class SessionCreateRequest(BaseModel):
    session_id: Optional[str] = None
    task_id: Optional[str] = None
