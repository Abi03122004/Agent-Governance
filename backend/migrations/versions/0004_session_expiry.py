"""Add expires_at to agent_sessions.

Revision ID: 0004_session_expiry
Revises: 0003_runtime_actions
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_session_expiry"
down_revision = "0003_runtime_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_agent_sessions_expires_at", "agent_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_sessions_expires_at", "agent_sessions")
    op.drop_column("agent_sessions", "expires_at")
