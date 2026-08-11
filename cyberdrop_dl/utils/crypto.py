from __future__ import annotations

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

EMPTY_IV = b"\0" * AES.block_size


def aes_cbc_encrypt(data: bytes, key: bytes, iv: bytes = EMPTY_IV) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(data)


def aes_cbc_decrypt(data: bytes, key: bytes, iv: bytes = EMPTY_IV) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)


def aes_unpad(data: bytes) -> bytes:
    return unpad(data, AES.block_size)
