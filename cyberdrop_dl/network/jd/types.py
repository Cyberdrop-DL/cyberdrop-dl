# ruff : noqa: N815
from __future__ import annotations

import dataclasses
from typing import Literal

from cyberdrop_dl.utils.dataclass import DictDataclass


@dataclasses.dataclass(slots=True, frozen=True, order=True, kw_only=True)
class JDDevice(DictDataclass):
    id: str
    name: str
    type: str


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class MyJDSession:
    login_secret: bytes
    device_secret: bytes
    token: str
    regain_token: str
    server_encrypt_token: bytes
    device_encrypt_token: bytes


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AddLinksQuery(DictDataclass):
    links: str
    assignJobID: bool | None = None
    autoExtract: bool | None = None
    autostart: bool | None = None
    deepDecrypt: bool | None = None
    destinationFolder: str | None = None
    downloadPassword: str | None = None
    extractPassword: str | None = None
    sourceUrl: str | None = None
    overwritePackagizerRules: bool | None = None
    packageName: str | None = None
    dataURLs: list[str] = dataclasses.field(default_factory=list)
    priority: Literal["HIGHEST", "HIGHER", "HIGH", "DEFAULT", "LOW", "LOWER", "LOWEST"] = "DEFAULT"
