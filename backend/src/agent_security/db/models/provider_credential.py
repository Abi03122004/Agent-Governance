"""Agent Provider Credential ORM Model for Encrypted Vault Storage."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from agent_security.db.base import Base


class AgentProviderCredentialModel(Base):
    """Encrypted storage for external LLM provider API credentials."""
    __tablename__ = "agent_provider_credentials"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(64), nullable=False)  # openai, gemini, anthropic
    encrypted_api_key = Column(Text, nullable=False)  # AES-256-GCM envelope
    key_fingerprint = Column(String(64), nullable=False)  # Safe masked fingerprint (e.g. sk-...1234)
    encryption_key_version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("AgentModel", back_populates="provider_credentials")

