"""Make audit_events fields nullable for lifecycle events.

Revision ID: 0005_audit_events_flexibility
Revises: 0004_session_expiry
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_audit_events_flexibility"
down_revision = "0004_session_expiry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("audit_events", "project_id", nullable=True)
    op.alter_column("audit_events", "agent_id", nullable=True)
    op.alter_column("audit_events", "session_id", nullable=True)
    op.alter_column("audit_events", "task_id", nullable=True)
    op.alter_column("audit_events", "action_id", nullable=True)
    op.alter_column("audit_events", "tool_name", nullable=True)
    op.alter_column("audit_events", "canonical_action_hash", nullable=True)
    op.alter_column("audit_events", "policy_decision", nullable=True)
    op.alter_column("audit_events", "execution_state", nullable=True)


def downgrade() -> None:
    op.alter_column("audit_events", "project_id", nullable=False)
    op.alter_column("audit_events", "agent_id", nullable=False)
    op.alter_column("audit_events", "session_id", nullable=False)
    op.alter_column("audit_events", "task_id", nullable=False)
    op.alter_column("audit_events", "action_id", nullable=False)
    op.alter_column("audit_events", "tool_name", nullable=False)
    op.alter_column("audit_events", "canonical_action_hash", nullable=False)
    op.alter_column("audit_events", "policy_decision", nullable=False)
    op.alter_column("audit_events", "execution_state", nullable=False)
