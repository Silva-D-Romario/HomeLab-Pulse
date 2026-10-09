import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from homelab_pulse.models.service import ServiceKind


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    kind: ServiceKind = ServiceKind.HTTP
    target_url: AnyHttpUrl
    enabled: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    kind: ServiceKind | None = None
    target_url: AnyHttpUrl | None = None
    enabled: bool | None = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    server_id: uuid.UUID
    name: str
    kind: ServiceKind
    target_url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

