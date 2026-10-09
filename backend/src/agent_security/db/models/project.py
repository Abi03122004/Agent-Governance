"""Project ORM Model."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from agent_security.db.base import Base


class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    organization = relationship("OrganizationModel", back_populates="projects")
    agents = relationship("AgentModel", back_populates="project", cascade="all, delete-orphan")
