import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from homelab_pulse.config import get_settings


class CredentialDecryptionError(RuntimeError):
    pass


def _cipher() -> Fernet:
    secret = get_settings().credential_encryption_secret.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    return _cipher().encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_api_key: str) -> str:
    try:
        return _cipher().decrypt(encrypted_api_key.encode()).decode()
    except InvalidToken as error:
        message = "Stored integration credential cannot be decrypted"
        raise CredentialDecryptionError(message) from error
