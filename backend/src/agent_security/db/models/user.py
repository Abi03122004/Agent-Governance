"""User and Membership ORM Models."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from agent_security.db.base import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    status = Column(String(32), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    memberships = relationship("MembershipModel", back_populates="user", cascade="all, delete-orphan")


class MembershipModel(Base):
    __tablename__ = "memberships"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(64), nullable=False)  # administrator, security_operator, approver, viewer
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("UserModel", back_populates="memberships")
    organization = relationship("OrganizationModel", back_populates="memberships")
