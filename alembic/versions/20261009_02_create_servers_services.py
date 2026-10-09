"""Create servers and services tables.

Revision ID: 20261009_02
Revises: 20261009_01
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261009_02"
down_revision: str | None = "20261009_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "servers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_servers_owner_name"),
    )
    op.create_index(op.f("ix_servers_owner_id"), "servers", ["owner_id"], unique=False)

    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("server_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "HTTP",
                "DOCKER",
                "JELLYFIN",
                "PORTAINER",
                "ARR",
                name="service_kind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_id", "name", name="uq_services_server_name"),
    )
    op.create_index(op.f("ix_services_server_id"), "services", ["server_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_services_server_id"), table_name="services")
    op.drop_table("services")
    op.drop_index(op.f("ix_servers_owner_id"), table_name="servers")
    op.drop_table("servers")
