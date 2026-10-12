import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from homelab_pulse.models.incident import IncidentStatus


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    status: IncidentStatus
    detail: str | None
    opened_at: datetime
    resolved_at: datetime | None
