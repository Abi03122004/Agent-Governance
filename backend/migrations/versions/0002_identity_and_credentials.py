"""identity_and_credentials

Revision ID: 0002_identity_and_credentials
Revises: 0001_initial_schema
Create Date: 2024-10-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_identity_and_credentials'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename tenants to organizations
    op.rename_table('tenants', 'organizations')
    op.add_column('organizations', sa.Column('status', sa.String(length=32), server_default='active', nullable=False))
    op.add_column('organizations', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.drop_column('organizations', 'is_active')

    # Update projects table
    op.alter_column('projects', 'tenant_id', new_column_name='organization_id')
    op.drop_constraint('projects_tenant_id_fkey', 'projects', type_='foreignkey')
    op.create_foreign_key('projects_organization_id_fkey', 'projects', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.add_column('projects', sa.Column('status', sa.String(length=32), server_default='active', nullable=False))
    op.add_column('projects', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.drop_column('projects', 'is_active')

    # Create users table
    op.create_table('users',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=256), nullable=False),
    sa.Column('display_name', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=32), server_default='active', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create memberships table
    op.create_table('memberships',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('organization_id', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memberships_organization_id'), 'memberships', ['organization_id'], unique=False)
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)

    # Update agents table
    op.alter_column('agents', 'tenant_id', new_column_name='organization_id')
    op.drop_constraint('agents_tenant_id_fkey', 'agents', type_='foreignkey')
    op.create_foreign_key('agents_organization_id_fkey', 'agents', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.add_column('agents', sa.Column('owner', sa.String(length=128), server_default='', nullable=False))
    op.add_column('agents', sa.Column('environment', sa.String(length=64), server_default='development', nullable=False))
    op.add_column('agents', sa.Column('purpose', sa.Text(), nullable=True))
    op.add_column('agents', sa.Column('status', sa.String(length=32), server_default='active', nullable=False))
    op.add_column('agents', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.drop_column('agents', 'role')
    op.drop_column('agents', 'is_active')
    op.drop_column('agents', 'is_suspended')

    # Create agent_credentials table
    op.create_table('agent_credentials',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('secret_hash', sa.String(length=128), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_credentials_agent_id'), 'agent_credentials', ['agent_id'], unique=False)

    # Update agent_sessions table
    op.alter_column('agent_sessions', 'tenant_id', new_column_name='organization_id')
    op.drop_constraint('agent_sessions_tenant_id_fkey', 'agent_sessions', type_='foreignkey')
    op.create_foreign_key('agent_sessions_organization_id_fkey', 'agent_sessions', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.add_column('agent_sessions', sa.Column('credential_id', sa.String(length=64), nullable=True))
    op.create_foreign_key('agent_sessions_credential_id_fkey', 'agent_sessions', 'agent_credentials', ['credential_id'], ['id'], ondelete='SET NULL')
    op.add_column('agent_sessions', sa.Column('status', sa.String(length=32), server_default='active', nullable=False))
    op.add_column('agent_sessions', sa.Column('correlation_id', sa.String(length=128), nullable=True))
    op.add_column('agent_sessions', sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('agent_sessions', sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_column('agent_sessions', 'created_at')
    op.drop_column('agent_sessions', 'expires_at')
    op.drop_column('agent_sessions', 'is_revoked')

    # Update policies table
    op.alter_column('policies', 'tenant_id', new_column_name='organization_id')
    op.drop_constraint('policies_tenant_id_fkey', 'policies', type_='foreignkey')
    op.create_foreign_key('policies_organization_id_fkey', 'policies', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')

    # Update approval_requests table
    op.alter_column('approval_requests', 'tenant_id', new_column_name='organization_id')
    op.drop_constraint('approval_requests_tenant_id_fkey', 'approval_requests', type_='foreignkey')
    op.create_foreign_key('approval_requests_organization_id_fkey', 'approval_requests', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')

    # Update audit_events table
    op.alter_column('audit_events', 'tenant_id', new_column_name='organization_id')
    op.drop_constraint('audit_events_tenant_id_fkey', 'audit_events', type_='foreignkey')
    op.create_foreign_key('audit_events_organization_id_fkey', 'audit_events', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.drop_index('ix_audit_tenant_timestamp', table_name='audit_events')
    op.create_index('ix_audit_organization_timestamp', 'audit_events', ['organization_id', 'timestamp'], unique=False)


def downgrade() -> None:
    pass
