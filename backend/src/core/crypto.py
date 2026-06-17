"""
AES-256-GCM symmetric encryption for storing OAuth provider tokens.
Key source: TOKEN_ENCRYPTION_KEY setting (base64-decoded to 32 bytes).
"""
import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


def _get_key() -> bytes:
    """Decode the AES-256 key from the environment / settings."""
    from src.core.config import settings  # local import to avoid circular deps

    raw = settings.TOKEN_ENCRYPTION_KEY
    if not raw:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not configured.")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError(
            f"TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes; got {len(key)}."
        )
    return key


def encrypt(plaintext: str) -> str:
    """
    Encrypt *plaintext* with AES-256-GCM.

    Returns a base64url-encoded string: nonce(12) + ciphertext + tag(16).
    The nonce is randomly generated per call so identical plaintexts
    produce different ciphertexts.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # ciphertext already contains the 16-byte auth tag appended by the library
    payload = nonce + ciphertext
    return base64.urlsafe_b64encode(payload).decode()


def decrypt(token: str) -> str:
    """
    Decrypt a value produced by :func:`encrypt`.

    Raises ``ValueError`` on authentication failure or malformed input.
    """
    key = _get_key()
    try:
        payload = base64.urlsafe_b64decode(token.encode())
        nonce, ciphertext = payload[:12], payload[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
    except Exception as exc:
        logger.warning("Token decryption failed: %s", exc)
        raise ValueError("Invalid or tampered encrypted token.") from exc