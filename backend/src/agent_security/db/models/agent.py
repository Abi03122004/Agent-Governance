"""Agent ORM Model."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from agent_security.db.base import Base


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    owner = Column(String(128), nullable=False)
    environment = Column(String(64), default="development", nullable=False)
    purpose = Column(Text, nullable=True)
    framework = Column(String(64), default="custom", nullable=False)  # openhands, langgraph, crewai, autogen, custom
    llm_provider = Column(String(64), default="openai", nullable=False)  # openai, gemini, anthropic
    default_model = Column(String(128), default="gpt-4o-mini", nullable=False)
    endpoint = Column(String(512), nullable=True)
    connection_status = Column(String(32), default="registered", nullable=False)  # registered, active, error, disconnected
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    governed_requests_count = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="active", nullable=False)  # active, revoked, suspended
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("ProjectModel", back_populates="agents")
    credentials = relationship("AgentCredentialModel", back_populates="agent", cascade="all, delete-orphan")
    provider_credentials = relationship("AgentProviderCredentialModel", back_populates="agent", cascade="all, delete-orphan")
