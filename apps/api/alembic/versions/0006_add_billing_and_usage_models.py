"""add billing and usage models

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Enum creation
    subscription_status_enum = postgresql.ENUM('ACTIVE', 'CANCELED', 'PAST_DUE', 'TRIALING', name='subscriptionstatus', create_type=False)
    subscription_status_enum.create(op.get_bind(), checkfirst=True)
    
    usage_event_type_enum = postgresql.ENUM('AI_GENERATION', 'RENDER', 'PUBLISH', 'SCHEDULED_PUBLISH', name='usageeventtype', create_type=False)
    usage_event_type_enum.create(op.get_bind(), checkfirst=True)

    # Tables
    op.create_table(
        'workspace_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_key', sa.String(length=50), nullable=False),
        sa.Column('status', subscription_status_enum, nullable=False, server_default='ACTIVE'),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id')
    )

    op.create_table(
        'usage_counters',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ai_generations_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('renders_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('publishes_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scheduled_publishes_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_counters_workspace_id'), 'usage_counters', ['workspace_id'], unique=False)

    op.create_table(
        'usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', usage_event_type_enum, nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('related_project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('related_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('related_job_id', sa.String(length=255), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_events_workspace_id'), 'usage_events', ['workspace_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_usage_events_workspace_id'), table_name='usage_events')
    op.drop_table('usage_events')
    
    op.drop_index(op.f('ix_usage_counters_workspace_id'), table_name='usage_counters')
    op.drop_table('usage_counters')
    
    op.drop_table('workspace_subscriptions')

    subscription_status_enum = postgresql.ENUM('ACTIVE', 'CANCELED', 'PAST_DUE', 'TRIALING', name='subscriptionstatus')
    subscription_status_enum.drop(op.get_bind(), checkfirst=True)
    
    usage_event_type_enum = postgresql.ENUM('AI_GENERATION', 'RENDER', 'PUBLISH', 'SCHEDULED_PUBLISH', name='usageeventtype')
    usage_event_type_enum.drop(op.get_bind(), checkfirst=True)
