"""Add RenderJob fields and enum statuses

Revision ID: 0002_add_render_job_fields
Revises: 0001_initial_schema
Create Date: 2026-05-03 16:55:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002_add_render_job_fields'
down_revision: str | None = '0001_initial_schema'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add project_id, input_payload, output_payload to render_jobs
    op.add_column('render_jobs', sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('render_jobs', sa.Column('input_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('render_jobs', sa.Column('output_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_index(op.f('ix_render_jobs_project_id'), 'render_jobs', ['project_id'], unique=False)
    op.create_foreign_key('fk_render_jobs_project_id_reel_projects', 'render_jobs', 'reel_projects', ['project_id'], ['id'])

    # Make project_id not nullable
    op.alter_column('render_jobs', 'project_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)


def downgrade() -> None:
    op.drop_constraint('fk_render_jobs_project_id_reel_projects', 'render_jobs', type_='foreignkey')
    op.drop_index(op.f('ix_render_jobs_project_id'), table_name='render_jobs')
    op.drop_column('render_jobs', 'output_payload')
    op.drop_column('render_jobs', 'input_payload')
    op.drop_column('render_jobs', 'project_id')
