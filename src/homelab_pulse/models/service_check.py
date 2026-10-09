import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from homelab_pulse.models.base import Base


class CheckStatus(StrEnum):
    UP = "up"
    DOWN = "down"


class ServiceCheck(Base):
    __tablename__ = "service_checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("services.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[CheckStatus] = mapped_column(
        Enum(CheckStatus, name="check_status", native_enum=False)
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    http_status: Mapped[int | None] = mapped_column(Integer, default=None)
    detail: Mapped[str | None] = mapped_column(String(500), default=None)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )

