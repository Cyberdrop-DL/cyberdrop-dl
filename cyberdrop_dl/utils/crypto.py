from __future__ import annotations

from Crypto.Cipher import AES

EMPTY_IV = b"\0" * AES.block_size


def aes_cbc_encrypt(data: bytes, key: bytes, iv: bytes = EMPTY_IV) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(data)


def aes_cbc_decrypt(data: bytes, key: bytes, iv: bytes = EMPTY_IV) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)
