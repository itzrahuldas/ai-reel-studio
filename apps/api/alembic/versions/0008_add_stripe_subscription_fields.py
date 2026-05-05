"""add stripe subscription fields

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(bind: sa.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'UNPAID'")
    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'INCOMPLETE'")
    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'INCOMPLETE_EXPIRED'")

    if not _has_column(bind, "workspace_subscriptions", "provider"):
        op.add_column(
            "workspace_subscriptions",
            sa.Column(
                "provider",
                sa.String(length=50),
                nullable=False,
                server_default="manual",
            ),
        )
    if not _has_column(bind, "workspace_subscriptions", "stripe_customer_id"):
        op.add_column(
            "workspace_subscriptions",
            sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        )
    if not _has_column(bind, "workspace_subscriptions", "stripe_subscription_id"):
        op.add_column(
            "workspace_subscriptions",
            sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        )
    if not _has_column(bind, "workspace_subscriptions", "stripe_price_id"):
        op.add_column(
            "workspace_subscriptions",
            sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        )
    if not _has_column(bind, "workspace_subscriptions", "stripe_checkout_session_id"):
        op.add_column(
            "workspace_subscriptions",
            sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
        )

    op.create_index(
        "ix_workspace_subscriptions_stripe_customer_id",
        "workspace_subscriptions",
        ["stripe_customer_id"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_workspace_subscriptions_stripe_subscription_id",
        "workspace_subscriptions",
        ["stripe_subscription_id"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_workspace_subscriptions_stripe_price_id",
        "workspace_subscriptions",
        ["stripe_price_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_workspace_subscriptions_stripe_checkout_session_id",
        "workspace_subscriptions",
        ["stripe_checkout_session_id"],
        unique=False,
        if_not_exists=True,
    )

    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column(
            "processing_status",
            sa.String(length=50),
            nullable=False,
            server_default="processing",
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id", name="uq_stripe_webhook_events_event_id"),
    )
    op.create_index(
        "ix_stripe_webhook_events_stripe_event_id",
        "stripe_webhook_events",
        ["stripe_event_id"],
        unique=False,
    )
    op.create_index(
        "ix_stripe_webhook_events_event_type",
        "stripe_webhook_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stripe_webhook_events_event_type", table_name="stripe_webhook_events")
    op.drop_index("ix_stripe_webhook_events_stripe_event_id", table_name="stripe_webhook_events")
    op.drop_table("stripe_webhook_events")

    op.drop_index(
        "ix_workspace_subscriptions_stripe_checkout_session_id",
        table_name="workspace_subscriptions",
        if_exists=True,
    )
    op.drop_index(
        "ix_workspace_subscriptions_stripe_price_id",
        table_name="workspace_subscriptions",
        if_exists=True,
    )
    op.drop_index(
        "ix_workspace_subscriptions_stripe_subscription_id",
        table_name="workspace_subscriptions",
        if_exists=True,
    )
    op.drop_index(
        "ix_workspace_subscriptions_stripe_customer_id",
        table_name="workspace_subscriptions",
        if_exists=True,
    )

    for column_name in (
        "stripe_checkout_session_id",
        "stripe_price_id",
        "stripe_subscription_id",
        "stripe_customer_id",
        "provider",
    ):
        op.drop_column("workspace_subscriptions", column_name)

    # PostgreSQL enum values are intentionally left in place for safe downgrades.
