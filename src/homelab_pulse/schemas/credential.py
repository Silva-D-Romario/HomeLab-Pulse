from datetime import datetime

from pydantic import BaseModel, Field


class ServiceCredentialUpdate(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)


class ServiceCredentialStatus(BaseModel):
    configured: bool
    updated_at: datetime | None
