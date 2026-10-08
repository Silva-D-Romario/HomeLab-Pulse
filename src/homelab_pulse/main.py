from fastapi import FastAPI

from homelab_pulse.api.health import router as health_router
from homelab_pulse.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API para monitoramento seguro de servicos e containers de homelab.",
    )
    application.include_router(health_router, prefix="/api/v1")
    return application


app = create_app()

