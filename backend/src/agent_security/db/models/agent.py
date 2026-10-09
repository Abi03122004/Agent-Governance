"""Agent ORM Model."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
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
    status = Column(String(32), default="active", nullable=False)  # active, revoked, suspended
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("ProjectModel", back_populates="agents")
    credentials = relationship("AgentCredentialModel", back_populates="agent", cascade="all, delete-orphan")
