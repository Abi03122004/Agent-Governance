"""Initial PostgreSQL schema for Agent Governance Platform.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-11 20:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])

    # 3. Agents table
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False, server_default="standard_agent"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])
    op.create_index("ix_agents_project_id", "agents", ["project_id"])
    op.create_index("ix_agents_is_suspended", "agents", ["is_suspended"])

    # 4. Agent Sessions table
    op.create_table(
        "agent_sessions",
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_agent_sessions_tenant_id", "agent_sessions", ["tenant_id"])
    op.create_index("ix_agent_sessions_agent_id", "agent_sessions", ["agent_id"])
    op.create_index("ix_agent_sessions_expires_at", "agent_sessions", ["expires_at"])
    op.create_index("ix_agent_sessions_is_revoked", "agent_sessions", ["is_revoked"])

    # 5. Tools table
    op.create_table(
        "tools",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(length=32), nullable=False, server_default="LOW"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parameter_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("cost_per_call", sa.Float(), nullable=False, server_default="0.0"),
        sa.PrimaryKeyConstraint("name"),
    )

    # 6. Policies table
    op.create_table(
        "policies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policies_tenant_id", "policies", ["tenant_id"])

    # 7. Policy Rules table
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("target_tool", sa.String(length=64), nullable=False, server_default="*"),
        sa.Column("condition_expr", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_rules_policy_id", "policy_rules", ["policy_id"])
    op.create_index("ix_policy_rules_priority", "policy_rules", ["priority"])

    # 8. Approval Requests table
    op.create_table(
        "approval_requests",
        sa.Column("ticket_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_action_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approver_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ticket_id"),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
    op.create_index("ix_approval_requests_action_id", "approval_requests", ["action_id"])
    op.create_index("ix_approval_requests_canonical_action_hash", "approval_requests", ["canonical_action_hash"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    # 9. Execution Records table
    op.create_table(
        "execution_records",
        sa.Column("execution_id", sa.String(length=128), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_action_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_decision", sa.String(length=32), nullable=False),
        sa.Column("execution_state", sa.String(length=32), nullable=False, server_default="SUBMITTED"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_ticket_id", sa.String(length=128), nullable=True),
        sa.Column("sanitized_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    op.create_index("ix_execution_records_action_id", "execution_records", ["action_id"])
    op.create_index("ix_execution_records_canonical_action_hash", "execution_records", ["canonical_action_hash"])
    op.create_index("ix_execution_records_execution_state", "execution_records", ["execution_state"])

    # 10. Audit Events table
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("canonical_action_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_decision", sa.String(length=32), nullable=False),
        sa.Column("execution_state", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="INFO"),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("previous_event_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_agent_id", "audit_events", ["agent_id"])
    op.create_index("ix_audit_events_session_id", "audit_events", ["session_id"])
    op.create_index("ix_audit_events_action_id", "audit_events", ["action_id"])
    op.create_index("ix_audit_events_event_hash", "audit_events", ["event_hash"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_tenant_timestamp", "audit_events", ["tenant_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("execution_records")
    op.drop_table("approval_requests")
    op.drop_table("policy_rules")
    op.drop_table("policies")
    op.drop_table("tools")
    op.drop_table("agent_sessions")
    op.drop_table("agents")
    op.drop_table("projects")
    op.drop_table("tenants")
