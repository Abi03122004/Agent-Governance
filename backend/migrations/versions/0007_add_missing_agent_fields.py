"""Add missing columns to agents table.

Revision ID: 0007_add_missing_agent_fields
Revises: 0006_approval_execution_token
Create Date: 2026-11-02 15:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_add_missing_agent_fields"
down_revision: Union[str, None] = "0006_approval_execution_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns that the API expects but are missing from the schema.
    op.add_column(
        "agents",
        sa.Column("framework", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("default_model", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("endpoint", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("connection_status", sa.String(length=32), server_default="unknown", nullable=False),
    )
    op.add_column(
        "agents",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("governed_requests_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("agents", "governed_requests_count")
    op.drop_column("agents", "last_seen_at")
    op.drop_column("agents", "connection_status")
    op.drop_column("agents", "endpoint")
    op.drop_column("agents", "default_model")
    op.drop_column("agents", "llm_provider")
    op.drop_column("agents", "framework")
