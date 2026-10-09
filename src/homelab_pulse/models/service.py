import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from homelab_pulse.models.base import Base

if TYPE_CHECKING:
    from homelab_pulse.models.server import Server


class ServiceKind(StrEnum):
    HTTP = "http"
    DOCKER = "docker"
    JELLYFIN = "jellyfin"
    PORTAINER = "portainer"
    ARR = "arr"


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("server_id", "name", name="uq_services_server_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("servers.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[ServiceKind] = mapped_column(
        Enum(ServiceKind, name="service_kind", native_enum=False),
        default=ServiceKind.HTTP,
    )
    target_url: Mapped[str] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    server: Mapped["Server"] = relationship(back_populates="services")
