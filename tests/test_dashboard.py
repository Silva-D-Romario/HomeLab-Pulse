from types import SimpleNamespace

import httpx
import pytest
from httpx import AsyncClient

from homelab_pulse.dashboard import (
    DashboardApiError,
    build_figures,
    build_services_table,
    create_server,
    create_service,
    delete_server_resource,
    delete_service_resource,
    fetch_all_services,
    fetch_servers,
    keep_available_value,
    load_resource_data,
    manage_server_resource,
    manage_service_resource,
    populate_server_form,
    populate_service_form,
    register_user,
    submit_server,
    submit_service,
    update_resource_options,
    update_server_resource,
    update_service_resource,
    update_session,
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
    result = submit_server(
        1,
        "jwt-token",
        0,
        "  Servidor principal  ",
        "  192.168.1.50  ",
        "  Homelab  ",
    )
    servers = [{"id": "server-1", "name": "Servidor principal"}]
    option_result = update_resource_options(servers, [], None, None, None)

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
    assert option_result[0] == [{"label": "Servidor principal", "value": "server-1"}]
    assert option_result[1] == "server-1"


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


def test_registration_and_crud_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []

    def response(method: str, url: str, status_code: int = 200) -> httpx.Response:
        return httpx.Response(status_code, request=httpx.Request(method, url), json={})

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        requests.append(("POST", url, kwargs))
        if url.endswith("/auth/login"):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"access_token": "new-token"},
            )
        return response("POST", url, 201)

    def fake_patch(url: str, **kwargs: object) -> httpx.Response:
        requests.append(("PATCH", url, kwargs))
        return response("PATCH", url)

    def fake_delete(url: str, **kwargs: object) -> httpx.Response:
        requests.append(("DELETE", url, kwargs))
        return response("DELETE", url, 204)

    monkeypatch.setattr("homelab_pulse.dashboard.httpx.post", fake_post)
    monkeypatch.setattr("homelab_pulse.dashboard.httpx.patch", fake_patch)
    monkeypatch.setattr("homelab_pulse.dashboard.httpx.delete", fake_delete)

    token = register_user("Romário", "romario@example.com", "SenhaForte@2026")
    update_server_resource("jwt", "server-1", "Homelab", "192.168.1.50", None)
    update_service_resource(
        "jwt", "service-1", "Jellyfin", "jellyfin", "http://jellyfin:8096", True
    )
    delete_service_resource("jwt", "service-1")
    delete_server_resource("jwt", "server-1")

    assert token == "new-token"
    assert [request[0] for request in requests] == [
        "POST",
        "POST",
        "PATCH",
        "PATCH",
        "DELETE",
        "DELETE",
    ]


def test_resource_loading_options_and_edit_forms(monkeypatch: pytest.MonkeyPatch) -> None:
    servers = [
        {
            "id": "server-1",
            "name": "Homelab",
            "host": "192.168.1.50",
            "description": "Servidor principal",
        }
    ]
    services = [
        {
            "id": "service-1",
            "server_id": "server-1",
            "server_name": "Homelab",
            "name": "Jellyfin",
            "kind": "jellyfin",
            "target_url": "http://jellyfin:8096",
            "enabled": True,
        }
    ]
    monkeypatch.setattr("homelab_pulse.dashboard.fetch_servers", lambda _token: servers)
    monkeypatch.setattr(
        "homelab_pulse.dashboard.fetch_all_services", lambda _token, _servers: services
    )

    loaded_servers, loaded_services = load_resource_data("jwt", 0, 0)
    options = update_resource_options(loaded_servers, loaded_services, None, None, None)

    assert options[1] == "server-1"
    assert options[3] == "server-1"
    assert options[5] == "service-1"
    assert options[4][0]["label"] == "Homelab — Jellyfin"
    assert keep_available_value(options[0], "missing") == "server-1"
    assert populate_server_form("server-1", servers) == (
        "Homelab",
        "192.168.1.50",
        "Servidor principal",
    )
    assert populate_service_form("service-1", services) == (
        "Jellyfin",
        "jellyfin",
        "http://jellyfin:8096",
        ["enabled"],
    )
    assert populate_server_form(None, servers) == ("", "", "")
    assert populate_service_form(None, services) == ("", None, "", [])
    assert load_resource_data(None, 0, 0) == ([], [])


def test_fetch_all_services_adds_server_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "homelab_pulse.dashboard.fetch_services",
        lambda _token, server_id: [
            {
                "id": f"service-{server_id}",
                "name": "Jellyfin",
            }
        ],
    )

    services = fetch_all_services(
        "jwt",
        [
            {"id": "server-1", "name": "Homelab"},
            {"id": "server-2", "name": "NAS"},
        ],
    )

    assert [service["server_name"] for service in services] == ["Homelab", "NAS"]


def test_session_callback_supports_registration_login_and_logout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("homelab_pulse.dashboard.register_user", lambda *_args: "new-token")
    monkeypatch.setattr("homelab_pulse.dashboard.authenticate", lambda *_args: "login-token")

    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="register-button")
    )
    registered = update_session(
        None,
        1,
        None,
        None,
        None,
        " Romário ",
        " romario@example.com ",
        "SenhaForte@2026",
        "SenhaForte@2026",
    )
    mismatch = update_session(
        None,
        1,
        None,
        None,
        None,
        "Romário",
        "romario@example.com",
        "SenhaForte@2026",
        "diferente",
    )

    monkeypatch.setattr("homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="login-button"))
    logged_in = update_session(
        1, None, None, "romario@example.com", "SenhaForte@2026", None, None, None, None
    )
    missing_login = update_session(1, None, None, None, None, None, None, None, None)

    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="logout-button")
    )
    logged_out = update_session(None, None, 1, None, None, None, None, None, None)

    assert registered == ("new-token", "", "Conta criada com sucesso.")
    assert mismatch[2] == "As senhas não coincidem."
    assert logged_in == ("login-token", "", "")
    assert missing_login[1] == "Informe e-mail e senha."
    assert logged_out == (None, "", "")


def test_management_callbacks_update_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    server_changes: dict[str, object] = {}
    service_changes: dict[str, object] = {}

    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="save-server-button")
    )
    monkeypatch.setattr(
        "homelab_pulse.dashboard.update_server_resource",
        lambda *args: server_changes.update(args=args),
    )
    server_result = manage_server_resource(
        1, None, "jwt", 0, "server-1", " Homelab ", " 192.168.1.50 ", " Principal "
    )

    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="save-service-button")
    )
    monkeypatch.setattr(
        "homelab_pulse.dashboard.update_service_resource",
        lambda *args: service_changes.update(args=args),
    )
    service_result = manage_service_resource(
        1,
        None,
        "jwt",
        0,
        "service-1",
        " Jellyfin ",
        "jellyfin",
        " http://host.docker.internal:8096 ",
        ["enabled"],
    )

    assert server_result[0] == 1
    assert server_changes["args"] == (
        "jwt",
        "server-1",
        "Homelab",
        "192.168.1.50",
        "Principal",
    )
    assert service_result[0] == 1
    assert service_changes["args"] == (
        "jwt",
        "service-1",
        "Jellyfin",
        "jellyfin",
        "http://host.docker.internal:8096",
        True,
    )


def test_management_callbacks_delete_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "homelab_pulse.dashboard.delete_server_resource",
        lambda token, resource_id: deleted.append((token, resource_id)),
    )
    monkeypatch.setattr(
        "homelab_pulse.dashboard.delete_service_resource",
        lambda token, resource_id: deleted.append((token, resource_id)),
    )

    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="delete-server-button")
    )
    server_result = manage_server_resource(None, 1, "jwt", 0, "server-1", None, None, None)

    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="delete-service-button")
    )
    service_result = manage_service_resource(None, 1, "jwt", 0, "service-1", None, None, None, [])

    assert deleted == [("jwt", "server-1"), ("jwt", "service-1")]
    assert server_result[0] == 1
    assert service_result[0] == 1


def test_forms_reject_missing_authentication_and_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="save-server-button")
    )
    assert submit_server(1, None, 0, None, None, None)[1] == "Entre novamente para cadastrar."
    assert submit_server(1, "jwt", 0, None, None, None)[1] == (
        "Informe o nome e o host do servidor."
    )
    assert submit_service(1, None, 0, None, None, "http", None)[1] == (
        "Entre novamente para cadastrar."
    )
    assert submit_service(1, "jwt", 0, None, None, "http", None)[1] == (
        "Selecione o servidor e informe nome e URL do serviço."
    )
    assert manage_server_resource(None, None, None, 0, None, None, None, None)[1] == (
        "Selecione um servidor."
    )
    assert manage_server_resource(None, None, "jwt", 0, "server-1", None, None, None)[1] == (
        "Informe o nome e o host do servidor."
    )
    monkeypatch.setattr(
        "homelab_pulse.dashboard.ctx", SimpleNamespace(triggered_id="save-service-button")
    )
    assert manage_service_resource(None, None, None, 0, None, None, None, None, [])[1] == (
        "Selecione um serviço."
    )
    assert (
        manage_service_resource(None, None, "jwt", 0, "service-1", None, None, None, [])[1]
        == "Informe nome, tipo e URL do serviço."
    )


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
