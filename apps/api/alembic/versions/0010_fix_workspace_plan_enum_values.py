"""fix workspace plan enum values

Revision ID: 0010_workspace_plan_enum
Revises: 0009
Create Date: 2026-05-06 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_workspace_plan_enum"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE workspaceplan ADD VALUE IF NOT EXISTS 'creator'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove enum values without rebuilding the type.
    # Keeping the extra value preserves existing data and makes downgrade non-destructive.
    pass
