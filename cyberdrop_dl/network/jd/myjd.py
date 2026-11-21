from __future__ import annotations

import dataclasses
import json
import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import __repo_url__
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.network.jd import Params, check_resp, prepare_api_json
from cyberdrop_dl.network.jd.crypto import compose_token, create_token, decrypt, encrypt, sign_hmac_sha256
from cyberdrop_dl.network.jd.types import AddLinksQuery, JDDevice, MyJDSession
from cyberdrop_dl.signature import dataclass_repr
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.network.http import HTTPClient


logger = logging.getLogger(__name__)
_AES_JSON = "application/aesjson; charset=utf-8"


@dataclass_repr("connected")
@dataclasses.dataclass(slots=True)
class MyJDAPI:
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.jdownloader.org")
    client: HTTPClient = dataclasses.field(repr=False)
    _session: MyJDSession | None = dataclasses.field(init=False, default=None, repr=False)

    @property
    def session(self) -> MyJDSession:
        if self._session is None:
            raise RuntimeError("API is not connected")
        return self._session

    @property
    def connected(self) -> bool:
        return self._session is not None

    async def connect(self, email: str, password: str) -> None:
        login_secret = create_token(email, password, "server")
        device_secret = create_token(email, password, "device")

        url = (self.ENTRYPOINT / "my/connect").with_query(email=email, appkey=__repo_url__)
        url = _sign_url(url, token=login_secret)

        resp = await self.get(url, token=login_secret)
        s_token, r_token = resp["sessiontoken"], resp["regaintoken"]
        self._session = MyJDSession(
            login_secret=login_secret,
            device_secret=device_secret,
            token=s_token,
            regain_token=r_token,
            server_encrypt_token=compose_token(login_secret, s_token),
            device_encrypt_token=compose_token(device_secret, s_token),
        )

    async def list_devices(self) -> list[JDDevice]:
        url = (self.ENTRYPOINT / "my/listdevices").with_query(sessiontoken=self.session.token)
        url = _sign_url(url, token=self.session.server_encrypt_token)
        resp = await self.get(url)
        return [JDDevice.from_dict(d) for d in resp["list"]]

    @staticmethod
    def find_device(
        devices: Iterable[JDDevice],
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
    ) -> JDDevice:
        if not (id or name):
            raise ValueError("Either device id or device name are required")

        for device in devices:
            if id is not None and device.id != id:
                continue
            if name is not None and device.name != name:
                continue

            return device

        raise LookupError("Device not found")

    async def get(self, url: AbsoluteHttpURL, token: bytes | None = None) -> Any:
        async with self.client.raw_request(url, headers={"User-Agent": CDL_USER_AGENT}) as resp:
            resp.content_type = _AES_JSON
            content = await resp.text()

        try:
            return _decode_aes_json(content, token or self.session.server_encrypt_token)
        except Exception:
            if resp.status != 200:
                raise RuntimeError(content) from None
            raise

    async def post(
        self,
        url: AbsoluteHttpURL,
        path: str,
        params: Params | None = None,
    ) -> Any:
        data = prepare_api_json(
            path,
            list(_dump_params(params or ())),
            rid=time.time_ns(),
        )

        async with self.client.raw_request(
            url,
            method="POST",
            headers={"Content-Type": _AES_JSON, "User-Agent": CDL_USER_AGENT},
            data=encrypt(_dump_aes_json(data), self.session.device_encrypt_token),
        ) as resp:
            resp.content_type = _AES_JSON
            content = await resp.text()

        try:
            return _decode_aes_json(content, self.session.device_encrypt_token)
        except Exception:
            if resp.status != 200:
                raise RuntimeError(content) from None
            raise


def _dump_aes_json(data: Any) -> bytes:
    return json.dumps(data).replace('"null"', "null").replace("'null'", "null").encode("utf-8")


def _dump_params(params: Params) -> Generator[Any]:
    for param in params:
        match param:
            case str():
                yield param
            case list() | tuple():
                yield list(_dump_params(param))
            case dict() | bool():
                yield json.dumps(param)
            case _:
                yield str(param)


def _decode_aes_json(content: str, token: bytes) -> Any:
    resp = decrypt(content, token)
    data = json.loads(resp)
    check_resp(data)
    return data.get("data", data)


@dataclasses.dataclass(slots=True, frozen=True)
class MyJDConnection:
    api: MyJDAPI
    device: JDDevice

    @property
    def _device_path(self) -> str:
        return "t_" + self.api.session.token + "_" + self.device.id

    def _build_url(self, path: str) -> AbsoluteHttpURL:
        return self.api.ENTRYPOINT / self._device_path / path.removeprefix("/")

    async def jd_version(self) -> int:
        return await self.api.get(
            self._build_url("/jd/version"),
            token=self.api.session.device_encrypt_token,
        )

    async def action(self, path: str, params: Params | None = None) -> dict[str, Any]:
        return await self.api.post(self._build_url(path), path=path, params=params)

    async def add_links(self, query: AddLinksQuery) -> int:
        resp = await self.action("/linkgrabberv2/addLinks", params=[dict(query)])
        return resp["id"]


def _sign_url(url: AbsoluteHttpURL, token: bytes, rid: int | None = None) -> AbsoluteHttpURL:
    url = url.update_query(rid=rid or time.time_ns())
    return url.update_query(signature=sign_hmac_sha256(url.raw_path_qs, token))
