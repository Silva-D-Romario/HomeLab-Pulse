import uuid

import jwt
import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from homelab_pulse.config import Settings, get_settings
from homelab_pulse.security import create_access_token, decode_access_token


def test_access_token_contains_and_validates_security_claims() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )

    assert decode_access_token(token) == user_id
    assert payload["type"] == "access"
    assert payload["jti"]
    assert payload["iat"] < payload["exp"]


def test_rejects_token_for_another_audience() -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": 4_102_444_800,
            "iat": 1_704_067_200,
            "jti": "test-id",
            "iss": settings.jwt_issuer,
            "aud": "another-api",
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(token)


def test_production_rejects_default_secrets_and_sqlite() -> None:
    with pytest.raises(ValidationError, match="Production requires strong secrets"):
        Settings(app_environment="production", _env_file=None)

    with pytest.raises(ValidationError, match="persistent database"):
        Settings(
            app_environment="production",
            jwt_secret="a" * 40,
            credential_encryption_secret="b" * 40,
            database_url="sqlite:///production.db",
            _env_file=None,
        )

    settings = Settings(
        app_environment="production",
        jwt_secret="a" * 40,
        credential_encryption_secret="b" * 40,
        database_url="postgresql://user:password@database.example/app",
        _env_file=None,
    )
    assert settings.database_url.startswith("postgresql+psycopg://")


@pytest.mark.anyio
async def test_api_responses_include_security_headers(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
