from __future__ import annotations

import dataclasses
import logging
import time
from typing import TYPE_CHECKING, Any

from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.network.jd import Params, check_resp, prepare_api_json
from cyberdrop_dl.network.jd.types import AddLinksQuery, JDDevice
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.network.http import HTTPClient

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

    def _build_url(self, path: str) -> AbsoluteHttpURL:
        return self.entrypoint / path.removeprefix("/")

    async def action(self, path: str, params: Params | None = None) -> Any:
        return await self.request_json(self._build_url(path), params=params)

    async def add_links(self, query: AddLinksQuery) -> int:
        resp = await self.action("/linkgrabberv2/addLinks", params=[dict(query)])
        return resp["id"]

    async def request_json(self, url: AbsoluteHttpURL, params: Params | None = None) -> Any:
        async with self.client.raw_request(
            url,
            json=prepare_api_json(url.path, params, rid=time.time_ns()) if params is not None else None,
            headers={"User-Agent": CDL_USER_AGENT},
        ) as resp:
            data = await resp.json()

        check_resp(data)
        return data["data"]

    async def jd_version(self) -> int:
        return await self.action("/jd/version")
