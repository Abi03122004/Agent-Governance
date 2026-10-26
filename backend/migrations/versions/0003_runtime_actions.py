"""Persist gateway decisions and one-time execution authorizations.

Revision ID: 0003_runtime_actions
Revises: 0002_identity_and_credentials
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_runtime_actions"
down_revision = "0002_identity_and_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_actions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("tool", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("resource", sa.String(256), nullable=False),
        sa.Column("normalized_action", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("action_digest", sa.String(80), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("execution_status", sa.String(32), nullable=False, server_default="not_executed"),
        sa.Column("result", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runtime_actions_organization_id", "runtime_actions", ["organization_id"])
    op.create_index("ix_runtime_actions_agent_id", "runtime_actions", ["agent_id"])
    op.create_index("ix_runtime_actions_session_id", "runtime_actions", ["session_id"])
    op.create_index("ix_runtime_actions_decision", "runtime_actions", ["decision"])
    op.create_index("ix_runtime_actions_digest", "runtime_actions", ["action_digest"])
    op.create_index("ix_runtime_activity_agent_created", "runtime_actions", ["agent_id", "created_at"])
    op.create_table(
        "execution_authorizations",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("action_id", sa.String(128), sa.ForeignKey("runtime_actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_execution_authorizations_action_id", "execution_authorizations", ["action_id"])
    op.create_index("ix_execution_authorizations_expires_at", "execution_authorizations", ["expires_at"])


def downgrade() -> None:
    op.drop_table("execution_authorizations")
    op.drop_table("runtime_actions")
