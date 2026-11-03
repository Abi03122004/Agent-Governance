"""Add execution token to approval requests.

Revision ID: 0006_approval_execution_token
Revises: 0005_audit_events_flexibility
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_approval_execution_token"
down_revision = "0005_audit_events_flexibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approval_requests",
        sa.Column("execution_token", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approval_requests", "execution_token")
