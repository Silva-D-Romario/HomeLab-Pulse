from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from homelab_pulse.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    application: str
    environment: str
    version: str
    status: str
    timestamp: datetime


@router.get("", response_model=HealthResponse, summary="Verifica a disponibilidade da API")
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        application=settings.app_name,
        environment=settings.app_environment,
        version=settings.app_version,
        status="UP",
        timestamp=datetime.now(UTC),
    )

