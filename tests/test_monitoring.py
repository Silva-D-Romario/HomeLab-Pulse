import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from homelab_pulse import agent
from homelab_pulse.config import get_settings
from homelab_pulse.docker_collector import fetch_containers
from homelab_pulse.models.service_check import CheckStatus
from homelab_pulse.monitoring.http_probe import ProbeResult, probe_http_service
from homelab_pulse.schemas.agent import ContainerSummary


async def create_monitored_service(client: AsyncClient, email: str) -> tuple[str, str]:
    password = "SenhaForte@2026"
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Monitor", "email": email, "password": password},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    server_response = await client.post(
        "/api/v1/servers",
        headers=headers,
        json={"name": "Servidor Monitorado", "host": "homelab.local"},
    )
    server_id = server_response.json()["id"]
    service_response = await client.post(
        f"/api/v1/servers/{server_id}/services",
        headers=headers,
        json={
            "name": "Stirling PDF",
            "kind": "http",
            "target_url": "http://stirling-pdf:8080",
        },
    )
    return token, service_response.json()["id"]


@pytest.mark.anyio
async def test_http_probe_reports_up_and_down() -> None:
    async def online_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, request=request)

    async with AsyncClient(transport=httpx.MockTransport(online_handler)) as online_client:
        online_result = await probe_http_service("https://service.example.com", online_client)

    async def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with AsyncClient(transport=httpx.MockTransport(offline_handler)) as offline_client:
        offline_result = await probe_http_service("https://service.example.com", offline_client)

    assert online_result.status == CheckStatus.UP
    assert online_result.http_status == 204
    assert online_result.response_time_ms is not None
    assert offline_result.status == CheckStatus.DOWN
    assert offline_result.http_status is None
    assert "connection refused" in (offline_result.detail or "")


@pytest.mark.anyio
async def test_check_endpoint_stores_history_and_enforces_ownership(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_token, service_id = await create_monitored_service(client, "monitor-owner@example.com")
    stranger_token, _ = await create_monitored_service(client, "monitor-stranger@example.com")

    async def fake_probe(_target_url: str) -> ProbeResult:
        return ProbeResult(CheckStatus.UP, 18, 200)

    monkeypatch.setattr("homelab_pulse.api.monitoring.probe_http_service", fake_probe)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    check_response = await client.post(
        f"/api/v1/services/{service_id}/check",
        headers=owner_headers,
    )
    history_response = await client.get(
        f"/api/v1/services/{service_id}/checks",
        headers=owner_headers,
    )
    stranger_response = await client.get(
        f"/api/v1/services/{service_id}/checks",
        headers=stranger_headers,
    )

    assert check_response.status_code == 201
    assert check_response.json()["status"] == "up"
    assert check_response.json()["response_time_ms"] == 18
    assert history_response.status_code == 200
    assert history_response.json()[0]["id"] == check_response.json()["id"]
    assert stranger_response.status_code == 404


@pytest.mark.anyio
async def test_docker_collector_maps_read_only_container_data() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.params["all"] == "true"
        return httpx.Response(
            200,
            request=request,
            json=[
                {
                    "Id": "abc123def456",
                    "Names": ["/jellyfin"],
                    "Image": "jellyfin/jellyfin:latest",
                    "State": "running",
                    "Status": "Up 2 hours",
                }
            ],
        )

    async with AsyncClient(transport=httpx.MockTransport(handler)) as docker_client:
        containers = await fetch_containers(docker_client)

    assert containers == [
        ContainerSummary(
            id="abc123def456",
            name="jellyfin",
            image="jellyfin/jellyfin:latest",
            state="running",
            status="Up 2 hours",
        )
    ]


@pytest.mark.anyio
async def test_docker_agent_requires_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch() -> list[ContainerSummary]:
        return [
            ContainerSummary(
                id="abc123",
                name="portainer",
                image="portainer/portainer-ce",
                state="running",
                status="Up 1 hour",
            )
        ]

    monkeypatch.setattr(agent, "fetch_containers", fake_fetch)
    async with AsyncClient(
        transport=ASGITransport(app=agent.app),
        base_url="http://agent",
    ) as agent_client:
        unauthorized = await agent_client.get("/api/v1/containers")
        authorized = await agent_client.get(
            "/api/v1/containers",
            headers={"Authorization": f"Bearer {get_settings().agent_token}"},
        )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()[0]["name"] == "portainer"
