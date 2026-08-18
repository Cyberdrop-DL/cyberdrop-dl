from __future__ import annotations

import dataclasses
import itertools
import json
import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

import yarl
from yarl._query import get_str_query_from_sequence_iterable

from cyberdrop_dl.clients.jd import check_resp, prepare_api_json

from .crypto import (
    create_token,
    decrypt,
    encrypt,
    sign_hmac_sha256,
    update_token,
)
from .types import JDDevice

if TYPE_CHECKING:
    from collections.abc import Iterable

    import aiohttp


logger = logging.getLogger(__name__)

type Params = dict[str, Any] | list[Any] | tuple[Any]


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class MyJDSession:
    login_secret: bytes
    device_secret: bytes
    token: str
    regain_token: str
    server_encrypt_token: bytes
    device_encrypt_token: bytes


@dataclasses.dataclass(slots=True)
class MyJDAPI:
    ENTRYPOINT: ClassVar[str] = "https://api.jdownloader.org"
    client: aiohttp.ClientSession
    _app_key: str = "https://github.com/NTFSvolume/async-jd"
    _session: MyJDSession | None = dataclasses.field(init=False, default=None)

    @property
    def session(self) -> MyJDSession:
        if self._session is None:
            raise RuntimeError("API is not connected")
        return self._session

    async def connect(self, email: str, password: str) -> None:
        login_secret = create_token(email, password, "server")
        device_secret = create_token(email, password, "device")

        path = _sign_path_qs(
            "/my/connect",
            ("email", email),
            ("appkey", self._app_key),
            token=login_secret,
        )
        resp = await self.request(self._build_url(path))
        s_token, r_token = resp["sessiontoken"], resp["regaintoken"]
        self._session = MyJDSession(
            login_secret=login_secret,
            device_secret=device_secret,
            token=s_token,
            regain_token=r_token,
            server_encrypt_token=update_token(login_secret, s_token),
            device_encrypt_token=update_token(device_secret, s_token),
        )

    async def list_devices(self) -> list[JDDevice]:
        path = _sign_path_qs(
            "/my/listdevices",
            ("sessiontoken", self.session.token),
            token=self.session.server_encrypt_token,
        )
        resp = await self.request(self._build_url(path))
        return [JDDevice(**d) for d in resp["list"]]

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

    async def get_device(
        self,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
    ) -> JDDevice:
        if not (id or name):
            raise ValueError("Either device id or device name are required")

        devices = await self.list_devices()
        return self.find_device(devices, id=id, name=name)

    async def request(self, url: yarl.URL) -> Any:
        async with await self.client.get(url) as resp:
            content = await resp.text()
            return self._decode_aes_json(content)

    async def request_json(self, url: yarl.URL, payload: Params | None = None) -> Any:
        data = prepare_api_json(
            url,
            payload or (),
            rid=int(url.query.get("rid") or time.time_ns()),
        )
        async with self.client.post(
            url,
            headers={"Content-Type": "application/aesjson-jd; charset=utf-8"},
            data=encrypt(self.session.device_encrypt_token, json.dumps(data).encode()),
        ) as resp:
            content = await resp.text()
            return self._decode_aes_json(content)

    def _decode_aes_json(self, content: str):
        token = self.session.server_encrypt_token
        response = decrypt(token, content)
        data = json.loads(response)
        check_resp(data)
        return data["data"]

    def _build_url(
        self,
        path: str,
        action: str | None = None,
        api: str | None = None,
    ) -> yarl.URL:
        api = api or self.ENTRYPOINT
        return yarl.URL(api + (action or "") + path)


def _sign_path_qs(path: str, *params: tuple[str, str | int], token: bytes) -> str:
    items = itertools.chain(params, [("rid", time.time_ns())])
    query = get_str_query_from_sequence_iterable(items)
    url = f"{path}?{query}"
    signature = sign_hmac_sha256(token, url)
    return f"{url}&signature={signature}"
