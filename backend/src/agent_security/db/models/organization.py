"""Organization ORM Model."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship

from agent_security.db.base import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("ProjectModel", back_populates="organization", cascade="all, delete-orphan")
    memberships = relationship("MembershipModel", back_populates="organization", cascade="all, delete-orphan")
