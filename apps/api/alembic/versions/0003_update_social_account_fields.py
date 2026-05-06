"""Update SocialAccount fields

Revision ID: 0003_social_account_fields
Revises: 0002_add_render_job_fields
Create Date: 2026-05-03 17:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003_social_account_fields'
down_revision: str | None = '0002_add_render_job_fields'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename and modify existing columns
    op.alter_column('social_accounts', 'user_id', new_column_name='connected_by_user_id')
    op.alter_column('social_accounts', 'platform_username', new_column_name='username')
    op.alter_column('social_accounts', 'platform_user_id', new_column_name='ig_user_id')
    op.alter_column('social_accounts', 'platform_page_id', new_column_name='page_id')

    # Drop old array column and add new JSONB ones
    op.drop_column('social_accounts', 'scopes')

    # Add new columns
    op.add_column('social_accounts', sa.Column('account_type', sa.String(length=50), nullable=True))
    op.add_column('social_accounts', sa.Column('page_name', sa.String(length=255), nullable=True))
    op.add_column('social_accounts', sa.Column('scopes_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('social_accounts', sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('social_accounts', sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Drop new columns
    op.drop_column('social_accounts', 'disconnected_at')
    op.drop_column('social_accounts', 'metadata_json')
    op.drop_column('social_accounts', 'scopes_json')
    op.drop_column('social_accounts', 'page_name')
    op.drop_column('social_accounts', 'account_type')

    # Add back old array column
    op.add_column('social_accounts', sa.Column('scopes', postgresql.ARRAY(sa.String()), autoincrement=False, nullable=True))

    # Revert renamed columns
    op.alter_column('social_accounts', 'page_id', new_column_name='platform_page_id')
    op.alter_column('social_accounts', 'ig_user_id', new_column_name='platform_user_id')
    op.alter_column('social_accounts', 'username', new_column_name='platform_username')
    op.alter_column('social_accounts', 'connected_by_user_id', new_column_name='user_id')
