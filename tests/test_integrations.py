import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.integration_crypto import decrypt_api_key
from homelab_pulse.models.service import ServiceKind
from homelab_pulse.models.service_check import CheckStatus
from homelab_pulse.models.service_credential import ServiceCredential
from homelab_pulse.monitoring.http_probe import ProbeResult
from homelab_pulse.monitoring.integrations import probe_integration_service


async def create_integration_service(
    client: AsyncClient,
    email: str,
    kind: str,
    name: str,
) -> tuple[str, str]:
    password = "SenhaForte@2026"
    await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
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
        json={"name": f"Servidor {name}", "host": f"{name.lower()}.local"},
    )
    service = await client.post(
        f"/api/v1/servers/{server.json()['id']}/services",
        headers=headers,
        json={
            "name": name,
            "kind": kind,
            "target_url": f"http://{name.lower()}:8080",
        },
    )
    return token, service.json()["id"]


@pytest.mark.anyio
async def test_credentials_are_encrypted_and_isolated_by_owner(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_token, service_id = await create_integration_service(
        client, "integration-owner@example.com", "arr", "Sonarr"
    )
    stranger_token, _ = await create_integration_service(
        client, "integration-stranger@example.com", "arr", "Radarr"
    )
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}
    api_key = "sonarr-secret-api-key"

    update = await client.put(
        f"/api/v1/services/{service_id}/credential",
        headers=owner_headers,
        json={"api_key": api_key},
    )
    status_response = await client.get(
        f"/api/v1/services/{service_id}/credential",
        headers=owner_headers,
    )
    stranger_response = await client.get(
        f"/api/v1/services/{service_id}/credential",
        headers=stranger_headers,
    )
    stored = await db_session.get(ServiceCredential, uuid.UUID(service_id))

    assert update.status_code == 200
    assert update.json()["configured"] is True
    assert "api_key" not in update.text
    assert status_response.json()["configured"] is True
    assert stranger_response.status_code == 404
    assert stored is not None
    assert stored.encrypted_api_key != api_key
    assert decrypt_api_key(stored.encrypted_api_key) == api_key

    replacement_key = "new-sonarr-secret-key"
    replaced = await client.put(
        f"/api/v1/services/{service_id}/credential",
        headers=owner_headers,
        json={"api_key": replacement_key},
    )
    await db_session.refresh(stored)
    assert replaced.status_code == 200
    assert decrypt_api_key(stored.encrypted_api_key) == replacement_key

    deleted = await client.delete(
        f"/api/v1/services/{service_id}/credential",
        headers=owner_headers,
    )
    cleared = await client.get(
        f"/api/v1/services/{service_id}/credential",
        headers=owner_headers,
    )
    assert deleted.status_code == 204
    assert cleared.json() == {"configured": False, "updated_at": None}


@pytest.mark.anyio
async def test_integration_probes_normalize_supported_services() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/System/Info/Public":
            return httpx.Response(
                200,
                request=request,
                json={"ProductName": "Jellyfin", "Version": "10.11", "ServerName": "Media"},
            )
        if request.url.path == "/api/system/status":
            return httpx.Response(404, request=request)
        if request.url.path == "/api/status":
            return httpx.Response(200, request=request, json={"Version": "2.39.0"})
        if request.url.path == "/api/v3/system/status":
            return httpx.Response(
                200,
                request=request,
                json={"appName": "Sonarr", "version": "4.0.15", "instanceName": "Series"},
            )
        return httpx.Response(500, request=request)

    async with AsyncClient(transport=httpx.MockTransport(handler)) as integration_client:
        jellyfin = await probe_integration_service(
            ServiceKind.JELLYFIN, "http://jellyfin:8096", "jellyfin-key", integration_client
        )
        portainer = await probe_integration_service(
            ServiceKind.PORTAINER, "https://portainer:9443", "portainer-key", integration_client
        )
        arr = await probe_integration_service(
            ServiceKind.ARR, "http://sonarr:8989", "sonarr-key", integration_client
        )

    assert jellyfin.status == CheckStatus.UP
    assert jellyfin.integration_data == {
        "product": "Jellyfin",
        "version": "10.11",
        "instance_name": "Media",
    }
    assert portainer.integration_data == {"product": "Portainer", "version": "2.39.0"}
    assert arr.integration_data == {
        "product": "Sonarr",
        "version": "4.0.15",
        "instance_name": "Series",
    }
    assert requests[0].headers["X-Emby-Token"] == "jellyfin-key"
    assert requests[-1].headers["X-API-Key"] == "sonarr-key"


@pytest.mark.anyio
async def test_arr_check_uses_decrypted_key_and_persists_metadata(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, service_id = await create_integration_service(
        client, "runner-integration@example.com", "arr", "Lidarr"
    )
    headers = {"Authorization": f"Bearer {token}"}
    api_key = "lidarr-secret-key"
    await client.put(
        f"/api/v1/services/{service_id}/credential",
        headers=headers,
        json={"api_key": api_key},
    )

    async def fake_probe(
        kind: ServiceKind,
        _target_url: str,
        received_api_key: str | None,
    ) -> ProbeResult:
        assert kind == ServiceKind.ARR
        assert received_api_key == api_key
        return ProbeResult(
            CheckStatus.UP,
            15,
            200,
            integration_data={"product": "Lidarr", "version": "2.13"},
        )

    monkeypatch.setattr(
        "homelab_pulse.monitoring.runner.probe_integration_service",
        fake_probe,
    )
    response = await client.post(f"/api/v1/services/{service_id}/check", headers=headers)

    assert response.status_code == 201
    assert response.json()["integration_data"] == {
        "product": "Lidarr",
        "version": "2.13",
    }


@pytest.mark.anyio
async def test_arr_probe_requires_a_credential() -> None:
    result = await probe_integration_service(ServiceKind.ARR, "http://sonarr:8989", None)

    assert result.status == CheckStatus.DOWN
    assert result.detail == "Integration credential not configured"


@pytest.mark.anyio
async def test_check_handles_an_unreadable_credential(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, service_id = await create_integration_service(
        client, "corrupted-credential@example.com", "arr", "Readarr"
    )
    headers = {"Authorization": f"Bearer {token}"}
    credential = ServiceCredential(
        service_id=uuid.UUID(service_id),
        encrypted_api_key="corrupted-value",
    )
    db_session.add(credential)
    await db_session.commit()

    response = await client.post(f"/api/v1/services/{service_id}/check", headers=headers)

    assert response.status_code == 201
    assert response.json()["status"] == "down"
    assert response.json()["detail"] == "Integration credential cannot be decrypted"


@pytest.mark.anyio
async def test_rejects_credentials_for_a_generic_http_service(client: AsyncClient) -> None:
    token, service_id = await create_integration_service(
        client, "generic-http@example.com", "http", "Website"
    )

    response = await client.put(
        f"/api/v1/services/{service_id}/credential",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "unused-secret-key"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "This service type does not support integration credentials"
