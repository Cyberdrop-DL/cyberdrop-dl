from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any

import yarl

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

    async def add_links(self, query: AddLinksQuery) -> dict[str, Any]:
        url = self.base_url / "linkgrabberv2/addLinks"
        return await self.request_json(url, json=dict(query))

    async def request_json(self, url: yarl.URL, json: dict[str, Any] | None = None) -> Any:
        async with self.client.post(url, json=json) as resp:
            data = await resp.json()
            data = data.get("data", data)
            if type(data) is dict and data.get("type") == "BAD_PARAMETERS":
                msg = f"BAD_PARAMETERS ({str(data)[:40]})"
                raise RuntimeError(msg)
            return data

    async def jd_version(self) -> int:
        url = self.base_url / "jd/version"
        return await self.request_json(url)


async def test() -> None:
    import aiohttp

    async with aiohttp.ClientSession() as client:
        jd_conn = DirectConnection(client)
        version = await jd_conn.jd_version()
        print(version)  # noqa: T201


if __name__ == "__main__":
    from cyberdrop_dl import aio

    aio.run(test())
