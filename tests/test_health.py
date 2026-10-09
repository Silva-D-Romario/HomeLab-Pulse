import pytest
from httpx import ASGITransport, AsyncClient

from homelab_pulse.main import app


@pytest.mark.anyio
async def test_health_check_returns_application_status() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["application"] == "HomeLab Pulse"
    assert payload["environment"] == "development"
    assert payload["version"] == "0.4.0"
    assert payload["status"] == "UP"
    assert payload["timestamp"]


@pytest.mark.anyio
async def test_openapi_documentation_is_available() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text
