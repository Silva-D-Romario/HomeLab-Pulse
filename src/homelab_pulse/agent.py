import hmac
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from homelab_pulse.config import get_settings
from homelab_pulse.docker_collector import fetch_containers
from homelab_pulse.schemas.agent import AgentHealth, ContainerSummary

bearer_scheme = HTTPBearer(auto_error=False)
app = FastAPI(
    title="HomeLab Pulse Docker Agent",
    version=get_settings().app_version,
    description="Agente autenticado para coleta somente leitura do Docker.",
)


async def verify_agent_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    expected_token = get_settings().agent_token
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not hmac.compare_digest(credentials.credentials, expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health", response_model=AgentHealth)
async def health() -> AgentHealth:
    return AgentHealth()


@app.get(
    "/api/v1/containers",
    response_model=list[ContainerSummary],
    dependencies=[Depends(verify_agent_token)],
)
async def list_containers() -> list[ContainerSummary]:
    try:
        return await fetch_containers()
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docker API unavailable",
        ) from error

