"""add real ai provider fields

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(bind: sa.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_column(bind, "reel_versions", "voiceover_asset_id"):
        op.add_column(
            "reel_versions",
            sa.Column("voiceover_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_reel_versions_voiceover_asset_id_media_assets",
            "reel_versions",
            "media_assets",
            ["voiceover_asset_id"],
            ["id"],
        )

    if not _has_column(bind, "generation_jobs", "provider"):
        op.add_column("generation_jobs", sa.Column("provider", sa.String(length=50), nullable=True))
        op.create_index(
            "ix_generation_jobs_provider",
            "generation_jobs",
            ["provider"],
            unique=False,
        )

    if not _has_column(bind, "generation_jobs", "provider_metadata_json"):
        op.add_column(
            "generation_jobs",
            sa.Column(
                "provider_metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    if not _has_column(bind, "generation_jobs", "error_code"):
        op.add_column("generation_jobs", sa.Column("error_code", sa.String(length=100), nullable=True))
        op.create_index(
            "ix_generation_jobs_error_code",
            "generation_jobs",
            ["error_code"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_error_code", table_name="generation_jobs", if_exists=True)
    op.drop_column("generation_jobs", "error_code")
    op.drop_column("generation_jobs", "provider_metadata_json")
    op.drop_index("ix_generation_jobs_provider", table_name="generation_jobs", if_exists=True)
    op.drop_column("generation_jobs", "provider")
    op.drop_constraint(
        "fk_reel_versions_voiceover_asset_id_media_assets",
        "reel_versions",
        type_="foreignkey",
    )
    op.drop_column("reel_versions", "voiceover_asset_id")
