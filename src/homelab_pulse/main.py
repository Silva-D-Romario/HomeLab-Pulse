from fastapi import FastAPI

from homelab_pulse.api.auth import router as auth_router
from homelab_pulse.api.health import router as health_router
from homelab_pulse.api.servers import router as servers_router
from homelab_pulse.api.services import router as services_router
from homelab_pulse.api.users import router as users_router
from homelab_pulse.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API para monitoramento seguro de servicos e containers de homelab.",
    )
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(servers_router, prefix="/api/v1")
    application.include_router(services_router, prefix="/api/v1")
    application.include_router(users_router, prefix="/api/v1")
    return application


app = create_app()
