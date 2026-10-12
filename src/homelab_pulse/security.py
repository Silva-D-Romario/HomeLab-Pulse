import uuid
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

import jwt
from pwdlib import PasswordHash

from homelab_pulse.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_password: str) -> bool:
    return password_hash.verify(password, encoded_password)


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": issued_at,
        "jti": token_urlsafe(16),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "exp", "iat", "jti", "iss", "aud", "type"]},
    )

    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("Invalid access token")

    try:
        return uuid.UUID(payload["sub"])
    except (TypeError, ValueError) as error:
        raise jwt.InvalidTokenError("Invalid token subject") from error
