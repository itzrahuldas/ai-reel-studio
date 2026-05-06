"""Add render settings and edit metadata to reel version

Revision ID: 0004_reel_editor_fields
Revises: 0003_social_account_fields
Create Date: 2026-05-03 23:20:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004_reel_editor_fields'
down_revision: str | None = '0003_social_account_fields'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new JSONB columns for editor
    op.add_column('reel_versions', sa.Column('render_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('reel_versions', sa.Column('edit_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Drop columns
    op.drop_column('reel_versions', 'edit_metadata')
    op.drop_column('reel_versions', 'render_settings')
