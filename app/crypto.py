"""AES-256-GCM encryption for cloud source fields in B50 uploads.

Shared secret key via ``B50_ENCRYPTION_KEY`` env var (base64-encoded 32-byte key).
If the key is not configured, fields are stored and returned as plaintext.
"""

from __future__ import annotations

import base64
import json
import os

ENCRYPTION_KEY: bytes | None = None
_raw = os.environ.get("B50_ENCRYPTION_KEY", "")
if _raw:
    ENCRYPTION_KEY = base64.b64decode(_raw)

FIELDS = ("serverUrl", "cardNo", "password", "pcbid")
GCM_NONCE_LEN = 12
GCM_TAG_LEN = 16


def _encrypt_value(plaintext: str) -> str:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes

    nonce = get_random_bytes(GCM_NONCE_LEN)
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_GCM, nonce=nonce)  # type: ignore[arg-type]
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
    return base64.b64encode(nonce + tag + ciphertext).decode("ascii")


def _decrypt_value(encoded: str) -> str:
    from Crypto.Cipher import AES

    raw = base64.b64decode(encoded)
    nonce, tag, ciphertext = raw[:GCM_NONCE_LEN], raw[GCM_NONCE_LEN:GCM_NONCE_LEN + GCM_TAG_LEN], raw[GCM_NONCE_LEN + GCM_TAG_LEN:]
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_GCM, nonce=nonce)  # type: ignore[arg-type]
    return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")


def encrypt_cloud_fields(payload_json: str) -> str:
    """Encrypt sensitive cloud source fields in the payload JSON string.

    Returns the original string unchanged when no encryption key is configured.
    """
    if ENCRYPTION_KEY is None:
        return payload_json

    data = json.loads(payload_json)
    for field in FIELDS:
        value = data.get(field)
        if value:
            data[field] = _encrypt_value(str(value))
    return json.dumps(data, ensure_ascii=False)


def decrypt_cloud_fields(data: dict) -> dict:
    """Decrypt sensitive cloud source fields in a payload dict (mutates in place)."""
    if ENCRYPTION_KEY is None:
        return data

    for field in FIELDS:
        value = data.get(field)
        if not value:
            continue
        try:
            data[field] = _decrypt_value(str(value))
        except Exception:
            # Field may already be plaintext (old data or key rotation).
            pass
    return data
