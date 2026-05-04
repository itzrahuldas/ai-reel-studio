"""bridge legacy billing down revision

Revision ID: 0005
Revises: 0005_add_scheduling_publish_job_fields
Create Date: 2026-05-04 00:05:00.000000

This no-op bridge preserves the already-published 0006 migration, whose
down_revision points at "0005".
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0005_add_scheduling_publish_job_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
