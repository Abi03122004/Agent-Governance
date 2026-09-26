"""SQLAlchemy ORM Models for Agent Governance Platform."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("ProjectModel", back_populates="organization", cascade="all, delete-orphan")
    memberships = relationship("MembershipModel", back_populates="organization", cascade="all, delete-orphan")


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
    role = Column(String(64), nullable=False) # administrator, security_operator, approver, viewer
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    user = relationship("UserModel", back_populates="memberships")
    organization = relationship("OrganizationModel", back_populates="memberships")


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    owner = Column(String(128), nullable=False)
    environment = Column(String(64), default="development", nullable=False)
    purpose = Column(Text, nullable=True)
    status = Column(String(32), default="active", nullable=False) # active, revoked, suspended
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("ProjectModel", back_populates="agents")
    credentials = relationship("AgentCredentialModel", back_populates="agent", cascade="all, delete-orphan")


class AgentCredentialModel(Base):
    __tablename__ = "agent_credentials"

    id = Column(String(64), primary_key=True)
    agent_id = Column(String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    secret_hash = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("AgentModel", back_populates="credentials")


class AgentSessionModel(Base):
    __tablename__ = "agent_sessions"

    session_id = Column(String(128), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id = Column(String(64), ForeignKey("agent_credentials.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), default="active", nullable=False) # active, completed, terminated
    correlation_id = Column(String(128), nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)


class ToolModel(Base):
    __tablename__ = "tools"

    name = Column(String(64), primary_key=True)
    description = Column(Text, default="", nullable=False)
    risk_level = Column(String(32), default="LOW", nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    parameter_schema = Column(JSONB, default=dict, nullable=False)
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


class ApprovalRequestModel(Base):
    __tablename__ = "approval_requests"

    ticket_id = Column(String(128), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    action_id = Column(String(128), nullable=False, index=True)
    canonical_action_hash = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="PENDING", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    approver_id = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)


class ExecutionRecordModel(Base):
    __tablename__ = "execution_records"

    execution_id = Column(String(128), primary_key=True)
    action_id = Column(String(128), nullable=False, index=True)
    canonical_action_hash = Column(String(64), nullable=False, index=True)
    policy_decision = Column(String(32), nullable=False)
    execution_state = Column(String(32), default="SUBMITTED", nullable=False, index=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    approval_ticket_id = Column(String(128), nullable=True)
    sanitized_output = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    event_id = Column(String(128), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), nullable=False)
    agent_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(128), nullable=False, index=True)
    task_id = Column(String(128), nullable=False)
    action_id = Column(String(128), nullable=False, index=True)
    tool_name = Column(String(64), nullable=False)
    canonical_action_hash = Column(String(64), nullable=False)
    policy_decision = Column(String(32), nullable=False)
    execution_state = Column(String(32), nullable=False)
    severity = Column(String(32), default="INFO", nullable=False)
    event_type = Column(String(64), nullable=False)
    details = Column(JSONB, default=dict, nullable=False)
    previous_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_organization_timestamp", "organization_id", "timestamp"),
    )


class RuntimeActionModel(Base):
    """Normalized action and policy decision, written before any execution."""
    __tablename__ = "runtime_actions"

    id = Column(String(128), primary_key=True)
    organization_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(64), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(128), nullable=False, index=True)
    tool = Column(String(64), nullable=False)
    operation = Column(String(64), nullable=False)
    resource = Column(String(256), nullable=False)
    normalized_action = Column(JSONB, nullable=False)
    action_digest = Column(String(80), nullable=False, index=True)
    decision = Column(String(32), nullable=False, index=True)
    reason_code = Column(String(64), nullable=False)
    correlation_id = Column(String(128), nullable=False, index=True)
    execution_status = Column(String(32), nullable=False, default="not_executed")
    result = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (Index("ix_runtime_activity_agent_created", "agent_id", "created_at"),)


class ExecutionAuthorizationModel(Base):
    """One-time server-side replay guard for an action-bound authorization."""
    __tablename__ = "execution_authorizations"

    id = Column(String(128), primary_key=True)
    action_id = Column(String(128), ForeignKey("runtime_actions.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
