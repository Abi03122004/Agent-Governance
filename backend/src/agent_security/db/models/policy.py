"""Policy and Tool ORM Models."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from agent_security.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class ToolModel(Base):
    __tablename__ = "tools"

    name = Column(String(64), primary_key=True)
    description = Column(Text, default="", nullable=False)
    risk_level = Column(String(32), default="LOW", nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    parameter_schema = Column(JSONType, default=dict, nullable=False)
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    cost_per_call = Column(Float, default=0.0, nullable=False)


class PolicyModel(Base):
    __tablename__ = "policies"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    rules = relationship("PolicyRuleModel", back_populates="policy", cascade="all, delete-orphan")


class PolicyRuleModel(Base):
    __tablename__ = "policy_rules"

    id = Column(String(64), primary_key=True)
    policy_id = Column(String(64), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    decision = Column(String(32), nullable=False)  # ALLOW, BLOCK, REQUIRE_APPROVAL, SUSPEND
    target_tool = Column(String(64), default="*", nullable=False)
    condition_expr = Column(Text, nullable=True)
    priority = Column(Integer, default=100, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    policy = relationship("PolicyModel", back_populates="rules")
