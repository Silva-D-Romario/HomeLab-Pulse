import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from homelab_pulse.models.service_check import CheckStatus


class DashboardServiceMetric(BaseModel):
    id: uuid.UUID
    name: str
    status: CheckStatus | None
    availability_percent: float | None
    average_response_time_ms: int | None
    last_checked_at: datetime | None
    integration_data: dict[str, Any] | None


class DashboardCheckPoint(BaseModel):
    service_id: uuid.UUID
    service_name: str
    status: CheckStatus
    response_time_ms: int | None
    checked_at: datetime


class DashboardResponse(BaseModel):
    generated_at: datetime
    window_hours: int
    servers_total: int
    services_total: int
    services_up: int
    services_down: int
    services_unknown: int
    open_incidents: int
    availability_percent: float | None
    average_response_time_ms: int | None
    services: list[DashboardServiceMetric]
    recent_checks: list[DashboardCheckPoint]
