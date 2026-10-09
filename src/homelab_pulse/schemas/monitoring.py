import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from homelab_pulse.models.service_check import CheckStatus


class ServiceCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    status: CheckStatus
    response_time_ms: int | None
    http_status: int | None
    detail: str | None
    checked_at: datetime

