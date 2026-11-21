from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Literal

from cyberdrop_dl.utils.crypto import aes_cbc_decrypt, aes_cbc_encrypt, aes_pad, aes_unpad


def create_token(email: str, password: str, domain: Literal["server", "device"]) -> bytes:
    data = email.lower() + password + domain.lower()
    return hashlib.sha256(data.encode("utf-8")).digest()


def sign_hmac_sha256(data: str, key: bytes) -> str:
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).hexdigest()


def encrypt(data: bytes, token: bytes) -> str:
    data = aes_pad(data)
    middle = len(token) // 2
    iv, key = token[:middle], token[middle:]
    return base64.b64encode(aes_cbc_encrypt(data, key, iv)).decode("utf-8")


def decrypt(data: str, token: bytes) -> bytes:
    middle = len(token) // 2
    iv, key = token[:middle], token[middle:]
    out = aes_cbc_decrypt(base64.b64decode(data), key, iv)
    return aes_unpad(out)


def compose_token(token: bytes, session_token: str) -> bytes:
    s_token = bytes.fromhex(session_token)
    return hashlib.sha256(token + s_token).digest()
