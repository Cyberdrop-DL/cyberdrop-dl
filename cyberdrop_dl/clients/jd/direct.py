from __future__ import annotations

import dataclasses
import logging
import time
from typing import TYPE_CHECKING, Any

from cyberdrop_dl.clients.jd import Params, check_resp, prepare_api_json
from cyberdrop_dl.clients.jd.types import AddLinksQuery, JDDevice
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.clients.http import HTTPClient

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True, frozen=True)
class DirectConnection:
    client: HTTPClient = dataclasses.field(repr=False)
    entrypoint: AbsoluteHttpURL = AbsoluteHttpURL("http://localhost:3128")  # noqa: RUF009
    device: JDDevice = dataclasses.field(
        init=False,
        default=JDDevice(
            id="local",
            name="Local JDownloader",
            type="jd",
        ),
    )

    async def action(self, path: str, params: Params | None = None) -> dict[str, Any]:
        url = self.entrypoint / path.removeprefix("/")
        return await self.request_json(url, json=params)

    async def add_links(self, query: AddLinksQuery) -> int:
        resp = await self.action("/linkgrabberv2/addLinks", params=[dict(query)])
        return resp["id"]

    async def request_json(self, url: AbsoluteHttpURL, json: Params | None = None) -> Any:
        async with self.client.request(
            url,
            json=prepare_api_json(url.path, json, rid=time.time_ns()) if json is not None else None,
        ) as resp:
            data = await resp.json()
            check_resp(data)
            return data["data"]

    async def jd_version(self) -> int:
        url = self.entrypoint / "jd/version"
        return await self.request_json(url)
