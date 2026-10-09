import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class ServerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class ServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    host: str
    description: str | None
    created_at: datetime
    updated_at: datetime

