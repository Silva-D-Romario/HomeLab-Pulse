import httpx
import pytest
from httpx import AsyncClient

from homelab_pulse.dashboard import (
    DashboardApiError,
    build_figures,
    build_services_table,
    create_server,
    create_service,
    fetch_servers,
    submit_server,
    submit_service,
    update_server_options,
    update_visibility,
)
from homelab_pulse.dashboard import app as dashboard_app
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


def test_empty_dashboard_explains_how_to_start() -> None:
    payload = {
        "services_up": 0,
        "services_down": 0,
        "services_unknown": 0,
        "services": [],
        "recent_checks": [],
    }

    figures = build_figures(payload)
    table = build_services_table([])

    assert all("Cadastre um servidor" in figure.layout.annotations[0].text for figure in figures)
    assert "Nenhum serviço cadastrado" in str(table)


def test_server_form_creates_resource_and_refreshes_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_server(token: str, name: str, host: str, description: str | None) -> None:
        captured.update(
            token=token,
            name=name,
            host=host,
            description=description,
        )

    monkeypatch.setattr("homelab_pulse.dashboard.create_server", fake_create_server)
    monkeypatch.setattr(
        "homelab_pulse.dashboard.fetch_servers",
        lambda _token: [{"id": "server-1", "name": "Servidor principal"}],
    )

    result = submit_server(
        1,
        "jwt-token",
        0,
        "  Servidor principal  ",
        "  192.168.1.50  ",
        "  Homelab  ",
    )
    options, selected = update_server_options("jwt-token", result[0], None)

    assert result == (
        1,
        "Servidor cadastrado com sucesso.",
        "hp-message hp-message-success",
        "",
        "",
        "",
    )
    assert captured == {
        "token": "jwt-token",
        "name": "Servidor principal",
        "host": "192.168.1.50",
        "description": "Homelab",
    }
    assert options == [{"label": "Servidor principal", "value": "server-1"}]
    assert selected == "server-1"


def test_service_form_creates_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_service(
        token: str,
        server_id: str,
        name: str,
        kind: str,
        target_url: str,
    ) -> None:
        captured.update(
            token=token,
            server_id=server_id,
            name=name,
            kind=kind,
            target_url=target_url,
        )

    monkeypatch.setattr("homelab_pulse.dashboard.create_service", fake_create_service)

    result = submit_service(
        1,
        "jwt-token",
        0,
        "server-1",
        "  Jellyfin  ",
        "jellyfin",
        "  http://192.168.1.50:8096  ",
    )

    assert result == (
        1,
        "Serviço cadastrado com sucesso.",
        "hp-message hp-message-success",
        "",
        "",
    )
    assert captured == {
        "token": "jwt-token",
        "server_id": "server-1",
        "name": "Jellyfin",
        "kind": "jellyfin",
        "target_url": "http://192.168.1.50:8096",
    }


def test_dashboard_api_helpers_send_token_and_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        requests.append((url, kwargs))
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json=[{"id": "server-1", "name": "Servidor principal"}],
        )

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        requests.append((url, kwargs))
        return httpx.Response(201, request=httpx.Request("POST", url), json={})

    monkeypatch.setattr("homelab_pulse.dashboard.httpx.get", fake_get)
    monkeypatch.setattr("homelab_pulse.dashboard.httpx.post", fake_post)

    servers = fetch_servers("jwt-token")
    create_server("jwt-token", "Principal", "192.168.1.50", None)
    create_service(
        "jwt-token",
        "server-1",
        "Jellyfin",
        "jellyfin",
        "http://192.168.1.50:8096",
    )

    assert servers[0]["id"] == "server-1"
    assert all(
        request[1]["headers"] == {"Authorization": "Bearer jwt-token"} for request in requests
    )
    assert requests[1][1]["json"] == {
        "name": "Principal",
        "host": "192.168.1.50",
        "description": None,
    }


@pytest.mark.parametrize(
    ("status_code", "expected_message"),
    [
        (401, "Sua sessão expirou. Entre novamente."),
        (409, "Já existe um serviço com esse nome neste servidor."),
        (422, "Informe uma URL completa, incluindo http:// ou https://."),
    ],
)
def test_create_service_translates_api_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_message: str,
) -> None:
    def fake_post(url: str, **_kwargs: object) -> httpx.Response:
        return httpx.Response(status_code, request=httpx.Request("POST", url))

    monkeypatch.setattr("homelab_pulse.dashboard.httpx.post", fake_post)

    with pytest.raises(DashboardApiError, match=expected_message):
        create_service("jwt-token", "server-1", "Jellyfin", "jellyfin", "URL inválida")


def test_dashboard_page_and_session_visibility() -> None:
    response = dashboard_app.server.test_client().get("/")
    stylesheet = dashboard_app.server.test_client().get("/assets/dashboard.css")

    assert response.status_code == 200
    assert b"HomeLab Pulse" in response.data
    assert stylesheet.status_code == 200
    assert b".hp-input" in stylesheet.data
    assert update_visibility("token")[1]["display"] == "block"
    assert update_visibility(None)[0]["display"] == "flex"
