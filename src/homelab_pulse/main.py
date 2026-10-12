from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from homelab_pulse.api.auth import router as auth_router
from homelab_pulse.api.credentials import router as credentials_router
from homelab_pulse.api.dashboard import router as dashboard_router
from homelab_pulse.api.health import router as health_router
from homelab_pulse.api.incidents import router as incidents_router
from homelab_pulse.api.monitoring import router as monitoring_router
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
    application.include_router(credentials_router, prefix="/api/v1")
    application.include_router(dashboard_router, prefix="/api/v1")
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(incidents_router, prefix="/api/v1")
    application.include_router(monitoring_router, prefix="/api/v1")
    application.include_router(servers_router, prefix="/api/v1")
    application.include_router(services_router, prefix="/api/v1")
    application.include_router(users_router, prefix="/api/v1")

    @application.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.app_environment.lower() in {"production", "prod"}:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    return application


app = create_app()
