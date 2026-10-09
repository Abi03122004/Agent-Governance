"""Security Context and Derived Identity."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AuthenticatedAgent:
    """Authenticated agent identity derived from cryptographic credentials."""
    organization_id: str
    project_id: str
    agent_id: str
    status: str


@dataclass(frozen=True)
class SecurityContext:
    """Request-scoped security context."""
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[str] = None
    agent: Optional[AuthenticatedAgent] = None
