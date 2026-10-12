"""Add integration data to service checks.

Revision ID: 20261012_06
Revises: 20261012_05
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_06"
down_revision: str | None = "20261012_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("service_checks", sa.Column("integration_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("service_checks", "integration_data")
