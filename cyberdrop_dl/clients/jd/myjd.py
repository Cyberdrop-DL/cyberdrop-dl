from __future__ import annotations

import dataclasses
import itertools
import json
import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

import yarl
from yarl._query import get_str_query_from_sequence_iterable

from cyberdrop_dl.clients.jd import Params, check_resp, prepare_api_json
from cyberdrop_dl.clients.jd.crypto import (
    create_token,
    decrypt,
    encrypt,
    sign_hmac_sha256,
    update_token,
)
from cyberdrop_dl.clients.jd.types import AddLinksQuery, JDDevice

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    import aiohttp


logger = logging.getLogger(__name__)


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

    @property
    def connected(self) -> bool:
        return self._session is not None

    async def connect(self, email: str, password: str) -> None:
        login_secret = create_token(email, password, "server")
        device_secret = create_token(email, password, "device")

        path = _sign_path_qs(
            "/my/connect",
            ("email", email),
            ("appkey", self._app_key),
            token=login_secret,
        )

        resp = await self.request(self._build_url(path), token=login_secret)
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

    async def request(self, url: yarl.URL, token: bytes | None = None) -> Any:
        logger.info("GET request to %s", url)
        async with await self.client.get(url) as resp:
            content = await resp.text()
            try:
                return _decode_aes_json(content, token or self.session.server_encrypt_token)
            except Exception:
                if resp.status != 200:
                    raise RuntimeError(content) from None
                raise

    async def request_json(
        self,
        url: yarl.URL,
        path: str | None = None,
        payload: Params | None = None,
    ) -> Any:
        data = prepare_api_json(
            path or url.path,
            list(_dump_params(payload or ())),
            rid=time.time_ns(),
        )

        logger.info("POST request to %s", url)
        async with self.client.post(
            url,
            headers={"Content-Type": "application/aesjson; charset=utf-8"},
            data=encrypt(self.session.device_encrypt_token, _dump_aes_json(data)),
        ) as resp:
            content = await resp.text()
            try:
                return _decode_aes_json(content, self.session.device_encrypt_token)
            except Exception:
                if resp.status != 200:
                    raise RuntimeError(content) from None
                raise

    def _build_url(self, path: str, action: str | None = None) -> yarl.URL:
        return yarl.URL(self.ENTRYPOINT + (action or "") + path)


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
    resp = decrypt(token, content)
    data = json.loads(resp)
    check_resp(data)
    return data.get("data", data)


@dataclasses.dataclass(slots=True, frozen=True)
class MyJDConnection:
    api: MyJDAPI
    device: JDDevice

    @property
    def _action_url(self) -> str:
        return "/t_" + self.api.session.token + "_" + self.device.id

    async def jd_version(self) -> int:
        path = "/jd/version"
        full_path = self.api._build_url(self._action_url + path)
        return await self.api.request(full_path, self.api.session.device_encrypt_token)

    async def action(self, path: str, params: Params | None = None) -> dict[str, Any]:
        full_path = self.api._build_url(self._action_url + path)
        return await self.api.request_json(full_path, path, payload=params)

    async def add_links(self, query: AddLinksQuery) -> int:
        resp = await self.action("/linkgrabberv2/addLinks", params=[dict(query)])
        return resp["id"]


def _sign_path_qs(path: str, *params: tuple[str, str | int], token: bytes) -> str:
    items = itertools.chain(params, [("rid", time.time_ns())])
    query = get_str_query_from_sequence_iterable(items)
    url = f"{path}?{query}"
    signature = sign_hmac_sha256(token, url)
    return f"{url}&signature={signature}"


async def test() -> None:
    import aiohttp

    email, password, device_name, link = sys.argv[1:5]
    async with aiohttp.ClientSession() as client:
        api = MyJDAPI(client)
        await api.connect(email, password)
        print(f"{api.connected = }")  # noqa: T201
        devices = await api.list_devices()
        logger.info("devices: %s", list(map(dict, devices)))
        device = api.find_device(devices, name=device_name)

        jd_conn = MyJDConnection(api, device)
        version = await jd_conn.jd_version()
        print(f"{version = }")  # noqa: T201
        job_id = await jd_conn.add_links(
            AddLinksQuery(
                autostart=False,
                links=link,
                overwritePackagizerRules=True,
            )
        )
        print(f"{job_id = }")  # noqa: T201


if __name__ == "__main__":
    import sys

    from cyberdrop_dl import aio
    from cyberdrop_dl.logs import setup_console_logging

    with setup_console_logging():
        aio.run(test())
