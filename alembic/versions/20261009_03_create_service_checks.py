"""Create service checks table.

Revision ID: 20261009_03
Revises: 20261009_02
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261009_03"
down_revision: str | None = "20261009_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("UP", "DOWN", name="check_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_service_checks_checked_at"),
        "service_checks",
        ["checked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_checks_service_id"),
        "service_checks",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_service_checks_service_id"), table_name="service_checks")
    op.drop_index(op.f("ix_service_checks_checked_at"), table_name="service_checks")
    op.drop_table("service_checks")
