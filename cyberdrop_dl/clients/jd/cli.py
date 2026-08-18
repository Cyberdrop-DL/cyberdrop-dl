"For testing only"

import dataclasses
import logging
from typing import Annotated

from cyclopts import App, Parameter

from cyberdrop_dl.clients.http import HTTPClient
from cyberdrop_dl.clients.jd.client import JDConfig, JDDeprecatedAPI, JDownloader
from cyberdrop_dl.logs import setup_console_logging
from cyberdrop_dl.url_objects import AbsoluteHttpURL

logger = logging.getLogger("cyberdrop_dl")

app = App()
myjd = App("myjd", "Connect using MyJDownloader servers")
direct = App("direct", "Connect over local LAN")

app.command(myjd)
app.command(direct)


@Parameter(name="*")
@dataclasses.dataclass(slots=True)
class MyJDAuth:
    username: str
    password: str
    device_name: str | None = None


def _http_client() -> HTTPClient:
    from cyberdrop_dl.clients.http import HTTPClient
    from cyberdrop_dl.config import Config

    return HTTPClient(Config())


@direct.command()
async def connect(api: Annotated[JDDeprecatedAPI | None, Parameter(name="*")] = None) -> None:
    jd = JDownloader(JDConfig(deprecated_api=api or JDDeprecatedAPI()))

    async with _http_client() as http:
        await jd.connect(http)
        app.console.print(jd._conn)


@direct.command()
async def add_links(
    link: str,
    api: Annotated[JDDeprecatedAPI | None, Parameter(name="*")] = None,
) -> None:
    "Add a new link to JD"
    jd = JDownloader(JDConfig(deprecated_api=api or JDDeprecatedAPI()))

    app.console.print(jd.config)
    async with _http_client() as http:
        await jd.connect(http)
        app.console.print(jd._conn)
        await jd.send(AbsoluteHttpURL(link), title="test CLI CDL")


@myjd.command(name="connect")
async def myjd_connect(auth: MyJDAuth) -> None:
    jd = JDownloader(JDConfig(username=auth.username, password=auth.password, device_name=auth.device_name))

    app.console.print(jd.config)
    async with _http_client() as http:
        await jd.connect(http)
        app.console.print(jd._conn)


@myjd.command(name="add_links")
async def myjd_add_links(link: str, auth: MyJDAuth) -> None:
    "Add a new link to JD"
    jd = JDownloader(
        JDConfig(
            username=auth.username,
            password=auth.password,
            device_name=auth.device_name,
        )
    )

    async with _http_client() as http:
        await jd.connect(http)
        await jd.send(AbsoluteHttpURL(link), title="test CLI CDL")


if __name__ == "__main__":
    from cyberdrop_dl.logs import setup_console_logging

    with setup_console_logging():
        app()
