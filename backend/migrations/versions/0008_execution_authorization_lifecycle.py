"""Add stateful claim/result lifecycle to execution authorizations.

Revision ID: 0008_execution_authorization_lifecycle
Revises: 0007_add_missing_agent_fields
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_execution_authorization_lifecycle"
down_revision = "0007_add_missing_agent_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_authorizations",
        sa.Column("state", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "execution_authorizations",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_authorizations",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_authorizations",
        sa.Column("result_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "execution_authorizations",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    # Preserve the meaning of existing records: a previously consumed legacy
    # token is never re-enabled by this migration.
    op.execute(
        "UPDATE execution_authorizations "
        "SET state = CASE WHEN used_at IS NULL THEN 'ISSUED' ELSE 'LEGACY_CONSUMED' END "
        "WHERE state IS NULL"
    )
    op.alter_column("execution_authorizations", "state", nullable=False, server_default="ISSUED")
    op.create_index(
        "ix_execution_authorizations_action_state",
        "execution_authorizations",
        ["action_id", "state"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_authorizations_action_state", table_name="execution_authorizations")
    op.drop_column("execution_authorizations", "last_error")
    op.drop_column("execution_authorizations", "result_hash")
    op.drop_column("execution_authorizations", "completed_at")
    op.drop_column("execution_authorizations", "claimed_at")
    op.drop_column("execution_authorizations", "state")
