"""Agent Session ORM Model."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String

from agent_security.db.base import Base


class AgentSessionModel(Base):
    __tablename__ = "agent_sessions"

    session_id = Column(String(128), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id = Column(String(64), ForeignKey("agent_credentials.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), default="active", nullable=False)  # active, completed, terminated
    correlation_id = Column(String(128), nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
