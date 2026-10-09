import pytest
from httpx import AsyncClient

USER_PAYLOAD = {
    "name": "Romário Silva",
    "email": "romario@example.com",
    "password": "SenhaForte@2026",
}


@pytest.mark.anyio
async def test_register_login_and_read_own_profile(client: AsyncClient) -> None:
    register_response = await client.post("/api/v1/auth/register", json=USER_PAYLOAD)

    assert register_response.status_code == 201
    registered_user = register_response.json()
    assert registered_user["name"] == USER_PAYLOAD["name"]
    assert registered_user["email"] == USER_PAYLOAD["email"]
    assert registered_user["role"] == "user"
    assert "password" not in registered_user
    assert "password_hash" not in registered_user

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": USER_PAYLOAD["email"], "password": USER_PAYLOAD["password"]},
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    profile_response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert profile_response.status_code == 200
    assert profile_response.json()["id"] == registered_user["id"]
    assert profile_response.json()["email"] == USER_PAYLOAD["email"]


@pytest.mark.anyio
async def test_rejects_duplicate_email(client: AsyncClient) -> None:
    first_response = await client.post("/api/v1/auth/register", json=USER_PAYLOAD)
    duplicate_response = await client.post(
        "/api/v1/auth/register",
        json={**USER_PAYLOAD, "email": "ROMARIO@example.com"},
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Email already registered"


@pytest.mark.anyio
async def test_rejects_invalid_login(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=USER_PAYLOAD)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": USER_PAYLOAD["email"], "password": "SenhaIncorreta@2026"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("authorization_header"),
    [None, "Bearer invalid-token"],
)
async def test_protects_profile_endpoint(
    client: AsyncClient,
    authorization_header: str | None,
) -> None:
    headers = {"Authorization": authorization_header} if authorization_header else {}

    response = await client.get("/api/v1/users/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
