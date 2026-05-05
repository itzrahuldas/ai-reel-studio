"""add usage idempotency constraints

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-04 00:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_rows(bind: sa.Connection, sql: str) -> bool:
    return bind.execute(sa.text(sql)).first() is not None


def _has_column(bind: sa.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("ALTER TYPE reelprojectstatus ADD VALUE IF NOT EXISTS 'rendered'")
    op.execute("ALTER TYPE reelprojectstatus ADD VALUE IF NOT EXISTS 'ready_to_publish'")

    if not _has_column(bind, "publish_jobs", "input_payload"):
        op.add_column(
            "publish_jobs",
            sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if not _has_column(bind, "publish_jobs", "output_payload"):
        op.add_column(
            "publish_jobs",
            sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    op.create_index(
        "ix_usage_counters_workspace_period",
        "usage_counters",
        ["workspace_id", "period_start", "period_end"],
        unique=False,
    )
    op.create_index(
        "ix_usage_events_workspace_type_job",
        "usage_events",
        ["workspace_id", "event_type", "related_job_id"],
        unique=False,
    )

    duplicate_counters = _has_rows(
        bind,
        """
        SELECT 1
        FROM usage_counters
        GROUP BY workspace_id, period_start, period_end
        HAVING COUNT(*) > 1
        LIMIT 1
        """,
    )
    if not duplicate_counters:
        op.create_index(
            "uq_usage_counters_workspace_period",
            "usage_counters",
            ["workspace_id", "period_start", "period_end"],
            unique=True,
        )

    duplicate_usage_events = _has_rows(
        bind,
        """
        SELECT 1
        FROM usage_events
        WHERE related_job_id IS NOT NULL
        GROUP BY workspace_id, event_type, related_job_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """,
    )
    if not duplicate_usage_events:
        op.create_index(
            "uq_usage_events_workspace_type_job",
            "usage_events",
            ["workspace_id", "event_type", "related_job_id"],
            unique=True,
            postgresql_where=sa.text("related_job_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(sa.text("DROP INDEX IF EXISTS uq_usage_events_workspace_type_job"))
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_usage_counters_workspace_period"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_usage_events_workspace_type_job"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_usage_counters_workspace_period"))

    if _has_column(bind, "publish_jobs", "output_payload"):
        op.drop_column("publish_jobs", "output_payload")
    if _has_column(bind, "publish_jobs", "input_payload"):
        op.drop_column("publish_jobs", "input_payload")
