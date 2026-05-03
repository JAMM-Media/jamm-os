# app/services/token_encryption.py

import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    from app.core.config import get_settings
    settings = get_settings()
    key = getattr(settings, "ENCRYPTION_KEY", None)
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Add a 32-byte URL-safe base64 key to your .env file."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a plaintext token string. Returns a URL-safe base64 ciphertext string."""
    try:
        fernet = _get_fernet()
        return fernet.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error("Token encryption failed: %s", type(e).__name__)
        raise


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Raises InvalidToken if tampered or wrong key."""
    try:
        fernet = _get_fernet()
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Token decryption failed: InvalidToken")
        raise
    except Exception as e:
        logger.error("Token decryption failed: %s", type(e).__name__)
        raise
