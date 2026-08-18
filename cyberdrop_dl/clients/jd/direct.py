from __future__ import annotations

import dataclasses
import logging
import time
from typing import TYPE_CHECKING, Any

import yarl

from cyberdrop_dl.clients.jd import Params, check_resp, prepare_api_json
from cyberdrop_dl.clients.jd.types import AddLinksQuery, JDDevice

if TYPE_CHECKING:
    import aiohttp

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class DirectConnection:
    client: aiohttp.ClientSession
    base_url: yarl.URL = yarl.URL("http://localhost:3128")  # noqa: RUF009
    device: JDDevice = dataclasses.field(
        init=False,
        default=JDDevice(
            id="local",
            name="Local JDownloader",
            type="jd",
        ),
    )

    async def action(self, path: str, params: Params | None = None) -> dict[str, Any]:
        url = self.base_url / path.removeprefix("/")
        return await self.request_json(url, json=params)

    async def add_links(self, query: AddLinksQuery) -> int:
        resp = await self.action("/linkgrabberv2/addLinks", params=[dict(query)])
        return resp["id"]

    async def request_json(self, url: yarl.URL, json: Params | None = None) -> Any:
        async with self.client.post(
            url,
            json=prepare_api_json(url.path, json, rid=time.time_ns()) if json is not None else None,
        ) as resp:
            data = await resp.json()
            check_resp(data)
            return data["data"]

    async def jd_version(self) -> int:
        url = self.base_url / "jd/version"
        return await self.request_json(url)


async def test(link: str) -> None:
    import aiohttp

    async with aiohttp.ClientSession() as client:
        jd_conn = DirectConnection(client)
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

    aio.run(test(sys.argv[1]))
