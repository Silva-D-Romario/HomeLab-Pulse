import pytest
from httpx import AsyncClient, Response


async def create_user_and_token(client: AsyncClient, email: str) -> str:
    password = "SenhaForte@2026"
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Usuário Teste", "email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_server(client: AsyncClient, token: str, name: str = "Servidor Casa") -> Response:
    response = await client.post(
        "/api/v1/servers",
        headers=authorization(token),
        json={
            "name": name,
            "host": "192.168.1.10",
            "description": "Servidor principal do homelab",
        },
    )
    assert response.status_code == 201
    return response


@pytest.mark.anyio
async def test_server_crud_is_scoped_to_authenticated_user(client: AsyncClient) -> None:
    token = await create_user_and_token(client, "owner@example.com")
    created_response = await create_server(client, token)
    server = created_response.json()

    list_response = await client.get("/api/v1/servers", headers=authorization(token))
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [server["id"]]

    update_response = await client.patch(
        f"/api/v1/servers/{server['id']}",
        headers=authorization(token),
        json={"host": "homelab.local"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["host"] == "homelab.local"

@pytest.mark.anyio
async def test_rejects_duplicate_server_name(client: AsyncClient) -> None:
    token = await create_user_and_token(client, "duplicates@example.com")
    await create_server(client, token)

    response = await client.post(
        "/api/v1/servers",
        headers=authorization(token),
        json={"name": "Servidor Casa", "host": "192.168.1.20"},
    )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_service_crud_and_server_cascade(client: AsyncClient) -> None:
    token = await create_user_and_token(client, "services@example.com")
    server = (await create_server(client, token)).json()

    create_response = await client.post(
        f"/api/v1/servers/{server['id']}/services",
        headers=authorization(token),
        json={
            "name": "Jellyfin",
            "kind": "jellyfin",
            "target_url": "http://jellyfin:8096",
        },
    )
    assert create_response.status_code == 201
    service = create_response.json()

    list_response = await client.get(
        f"/api/v1/servers/{server['id']}/services",
        headers=authorization(token),
    )
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == service["id"]

    update_response = await client.patch(
        f"/api/v1/services/{service['id']}",
        headers=authorization(token),
        json={"enabled": False, "kind": "http"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["enabled"] is False
    assert update_response.json()["kind"] == "http"

    delete_response = await client.delete(
        f"/api/v1/servers/{server['id']}",
        headers=authorization(token),
    )
    assert delete_response.status_code == 204

    missing_service_response = await client.get(
        f"/api/v1/services/{service['id']}",
        headers=authorization(token),
    )
    assert missing_service_response.status_code == 404


@pytest.mark.anyio
async def test_user_cannot_access_another_users_resources(client: AsyncClient) -> None:
    owner_token = await create_user_and_token(client, "first@example.com")
    stranger_token = await create_user_and_token(client, "second@example.com")
    server = (await create_server(client, owner_token, "Servidor Privado")).json()
    service_response = await client.post(
        f"/api/v1/servers/{server['id']}/services",
        headers=authorization(owner_token),
        json={
            "name": "Portainer",
            "kind": "portainer",
            "target_url": "https://portainer.example.com",
        },
    )
    assert service_response.status_code == 201
    service = service_response.json()

    stranger_list = await client.get("/api/v1/servers", headers=authorization(stranger_token))
    stranger_server = await client.get(
        f"/api/v1/servers/{server['id']}",
        headers=authorization(stranger_token),
    )
    stranger_service = await client.get(
        f"/api/v1/services/{service['id']}",
        headers=authorization(stranger_token),
    )
    stranger_create_service = await client.post(
        f"/api/v1/servers/{server['id']}/services",
        headers=authorization(stranger_token),
        json={
            "name": "Invasão",
            "kind": "http",
            "target_url": "https://example.com",
        },
    )
    stranger_delete = await client.delete(
        f"/api/v1/servers/{server['id']}",
        headers=authorization(stranger_token),
    )

    assert stranger_list.json() == []
    assert stranger_server.status_code == 404
    assert stranger_service.status_code == 404
    assert stranger_create_service.status_code == 404
    assert stranger_delete.status_code == 404
