from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Literal

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def create_token(email: str, password: str, domain: Literal["server", "device"]) -> bytes:
    data = email.lower() + password + domain.lower()
    return hashlib.sha256(data.encode("utf-8")).digest()


def sign_hmac_sha256(key: bytes, url: str) -> str:
    return hmac.new(key, url.encode("utf-8"), hashlib.sha256).hexdigest()


def encrypt(secret_token: bytes, data: bytes) -> str:
    data = pad(data, AES.block_size)
    middle = len(secret_token) // 2
    init_vector, key = secret_token[:middle], secret_token[middle:]
    cypher = AES.new(key, AES.MODE_CBC, init_vector)
    return base64.b64encode(cypher.encrypt(data)).decode("utf-8")


def decrypt(secret_token: bytes, data: str) -> bytes:
    middle = len(secret_token) // 2
    init_vector, key = secret_token[:middle], secret_token[middle:]
    cypher = AES.new(key, AES.MODE_CBC, init_vector)
    out = cypher.decrypt(base64.b64decode(data))
    return unpad(out, AES.block_size)


def update_token(token: bytes, session_token: str) -> bytes:
    s_token = bytes.fromhex(session_token)
    return hashlib.sha256(token + s_token).digest()
