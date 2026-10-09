"""Human-in-the-Loop (HITL) Cryptographic Approval Models."""

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
from agent_security.domain.enums import ApprovalStatus


class HumanApprover(BaseModel):
    """Authenticated human operator authorized to review actions."""
    id: str = Field(..., min_length=3, max_length=64)
    organization_id: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=5, max_length=128)
    role: str = Field(default="security_approver", max_length=64)


class ApprovalRequest(BaseModel):
    """A tamper-resistant approval request bound cryptographically to an action hash."""
    ticket_id: str = Field(..., min_length=3, max_length=128)
    organization_id: Optional[str] = Field(default="", max_length=64)
    action_id: str = Field(..., min_length=3, max_length=128)
    canonical_action_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 canonical hash of action payload")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    decided_at: Optional[datetime] = None
    approver_id: Optional[str] = None
    reason: Optional[str] = None

    def __init__(self, **data: Any):
        if "tenant_id" in data and "organization_id" not in data:
            data["organization_id"] = data.pop("tenant_id")
        super().__init__(**data)

    @property
    def tenant_id(self) -> str:
        return self.organization_id or ""

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Check whether the approval request has exceeded its TTL."""
        current = now or datetime.now(timezone.utc)
        return current >= self.expires_at

    def can_be_approved(self, now: Optional[datetime] = None) -> bool:
        """Check whether this approval is eligible for sign-off."""
        return self.status == ApprovalStatus.PENDING and not self.is_expired(now)
