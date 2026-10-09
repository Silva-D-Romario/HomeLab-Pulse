import uuid
from datetime import UTC, datetime, timedelta

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
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_minutes)
    payload = {"sub": str(user_id), "exp": expires_at, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("Invalid access token")

    try:
        return uuid.UUID(payload["sub"])
    except (TypeError, ValueError) as error:
        raise jwt.InvalidTokenError("Invalid token subject") from error

