import pytest
from httpx import AsyncClient

from homelab_pulse.dashboard import app as dashboard_app
from homelab_pulse.dashboard import build_figures, update_visibility
from homelab_pulse.models.service_check import CheckStatus
from homelab_pulse.monitoring.http_probe import ProbeResult


async def create_user_service(
    client: AsyncClient,
    email: str,
    service_name: str,
) -> tuple[str, str]:
    password = "SenhaForte@2026"
    await client.post(
        "/api/v1/auth/register",
        json={"name": service_name, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    server = await client.post(
        "/api/v1/servers",
        headers=headers,
        json={"name": f"Servidor {service_name}", "host": f"{service_name.lower()}.local"},
    )
    service = await client.post(
        f"/api/v1/servers/{server.json()['id']}/services",
        headers=headers,
        json={
            "name": service_name,
            "kind": "http",
            "target_url": f"http://{service_name.lower()}:8080",
        },
    )
    return token, service.json()["id"]


@pytest.mark.anyio
async def test_dashboard_aggregates_only_current_user_data(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_token, owner_service_id = await create_user_service(
        client, "dashboard-owner@example.com", "Jellyfin"
    )
    stranger_token, stranger_service_id = await create_user_service(
        client, "dashboard-stranger@example.com", "Portainer"
    )
    results = iter(
        [
            ProbeResult(CheckStatus.UP, 10, 200),
            ProbeResult(CheckStatus.DOWN, 30, 503, "HTTP 503"),
            ProbeResult(CheckStatus.UP, 5, 200),
        ]
    )

    async def fake_probe(_target_url: str) -> ProbeResult:
        return next(results)

    monkeypatch.setattr("homelab_pulse.monitoring.runner.probe_http_service", fake_probe)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}
    await client.post(f"/api/v1/services/{owner_service_id}/check", headers=owner_headers)
    await client.post(f"/api/v1/services/{owner_service_id}/check", headers=owner_headers)
    await client.post(f"/api/v1/services/{stranger_service_id}/check", headers=stranger_headers)

    response = await client.get("/api/v1/dashboard", headers=owner_headers)
    unauthorized = await client.get("/api/v1/dashboard")
    payload = response.json()

    assert response.status_code == 200
    assert unauthorized.status_code == 401
    assert payload["servers_total"] == 1
    assert payload["services_total"] == 1
    assert payload["services_down"] == 1
    assert payload["open_incidents"] == 1
    assert payload["availability_percent"] == 50.0
    assert payload["average_response_time_ms"] == 20
    assert {check["service_name"] for check in payload["recent_checks"]} == {"Jellyfin"}


def test_dashboard_builds_three_plotly_figures() -> None:
    payload = {
        "services_up": 1,
        "services_down": 1,
        "services_unknown": 0,
        "services": [
            {
                "name": "Jellyfin",
                "availability_percent": 99.5,
            }
        ],
        "recent_checks": [
            {
                "service_name": "Jellyfin",
                "response_time_ms": 24,
                "checked_at": "2026-10-11T10:00:00Z",
            }
        ],
    }

    status, availability, latency = build_figures(payload)

    assert status.data[0].type == "pie"
    assert availability.data[0].type == "bar"
    assert latency.data[0].type == "scatter"


def test_dashboard_page_and_session_visibility() -> None:
    response = dashboard_app.server.test_client().get("/")

    assert response.status_code == 200
    assert b"HomeLab Pulse" in response.data
    assert update_visibility("token")[1]["display"] == "block"
    assert update_visibility(None)[0]["display"] == "flex"
