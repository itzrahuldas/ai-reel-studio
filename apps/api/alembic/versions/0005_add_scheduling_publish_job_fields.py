"""Add scheduling publish job fields

Revision ID: 0005_scheduling_fields
Revises: 0004_reel_editor_fields
Create Date: 2026-05-03 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_scheduling_fields'
down_revision: Union[str, None] = '0004_reel_editor_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # We alter the publish_job_status type manually to add new enum values
    op.execute("ALTER TYPE publishjobstatus ADD VALUE IF NOT EXISTS 'scheduled'")
    op.execute("ALTER TYPE publishjobstatus ADD VALUE IF NOT EXISTS 'reconnect_required'")

    op.add_column('publish_jobs', sa.Column('schedule_timezone', sa.String(length=50), nullable=True))
    op.add_column('publish_jobs', sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('publish_jobs', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('publish_jobs', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('publish_jobs', sa.Column('cancel_reason', sa.String(length=255), nullable=True))
    op.add_column('publish_jobs', sa.Column('execution_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('publish_jobs', sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('publish_jobs', 'next_attempt_at')
    op.drop_column('publish_jobs', 'execution_attempts')
    op.drop_column('publish_jobs', 'cancel_reason')
    op.drop_column('publish_jobs', 'cancelled_at')
    op.drop_column('publish_jobs', 'locked_at')
    op.drop_column('publish_jobs', 'queued_at')
    op.drop_column('publish_jobs', 'schedule_timezone')
    
    # Removing enum values in postgres is tricky, we'll skip it for downgrade
