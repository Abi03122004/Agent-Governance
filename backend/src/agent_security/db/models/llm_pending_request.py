"""Pending LLM Request ORM Model for Human-in-the-Loop Governance."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from agent_security.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class LLMPendingRequestModel(Base):
    """Secure persistence for LLM proxy requests paused awaiting human authorization."""
    __tablename__ = "llm_pending_requests"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    approval_ticket_id = Column(String(64), ForeignKey("approval_requests.ticket_id", ondelete="SET NULL"), nullable=True, index=True)
    request_digest = Column(String(64), nullable=False, index=True)  # SHA-256 canonical digest of LLM request
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    request_payload = Column(JSONType, nullable=False)
    status = Column(String(32), default="PENDING_APPROVAL", nullable=False)  # PENDING_APPROVAL, APPROVED, REJECTED, EXECUTED, EXPIRED
    reason_code = Column(String(64), nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)

