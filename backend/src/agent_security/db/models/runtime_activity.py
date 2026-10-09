"""Runtime Activity, Approval, Execution, and Audit Models."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from agent_security.db.base import Base


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
