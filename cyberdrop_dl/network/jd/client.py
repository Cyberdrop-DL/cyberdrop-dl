from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Self

from cyberdrop_dl.exceptions import JDownloaderError
from cyberdrop_dl.network.jd.direct import DirectConnection
from cyberdrop_dl.network.jd.myjd import MyJDAPI, MyJDConnection
from cyberdrop_dl.network.jd.types import AddLinksQuery
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    import yarl

    from cyberdrop_dl.config import Config
    from cyberdrop_dl.network.http import HTTPClient


logger = logging.getLogger(__name__)


class Connection(Protocol):
    async def add_links(self, query: AddLinksQuery) -> int: ...

    async def jd_version(self) -> int: ...


def direct_connect(client: HTTPClient, host: str, port: int = 3128) -> DirectConnection:
    return DirectConnection(client, AbsoluteHttpURL(f"http://{host}:{port}"))


async def myjd_connect(
    client: HTTPClient,
    *,
    email: str,
    password: str,
    device_id: str | None = None,
    device_name: str | None = None,
) -> MyJDConnection:
    api = MyJDAPI(client)
    await api.connect(email, password)
    devices = await api.list_devices()
    logger.debug("JDownloader devices: %s", list(map(dict, devices)))
    device = api.find_device(devices, name=device_name, id=device_id)
    return MyJDConnection(api, device)


async def connect(client: HTTPClient, config: JDConfig) -> Connection:
    if config.deprecated_api:
        return direct_connect(client, config.deprecated_api.host, config.deprecated_api.port)

    if config.email and config.password and config.device_name:
        return await myjd_connect(
            client,
            email=config.email,
            password=config.password,
            device_name=config.device_name,
        )

    raise JDownloaderError("JDownloader credentials were not provided")


@dataclasses.dataclass(frozen=True, slots=True)
class JDDeprecatedAPI:
    host: str = "localhost"
    port: int = 3128

    @classmethod
    def from_url(cls, url: yarl.URL) -> Self:
        return cls(host=url.host or "localhost", port=url.explicit_port or 3128)


@dataclasses.dataclass(frozen=True, slots=True)
class JDConfig:
    enabled: bool = True
    email: str | None = None
    password: str | None = None
    device_name: str | None = None
    download_dir: Path = Path("downloads")
    autostart: bool = False
    whitelist: tuple[str, ...] = ()
    deprecated_api: JDDeprecatedAPI | None = None


@dataclasses.dataclass(slots=True)
class JDownloader:
    """Class that handles connecting and sending links to JDownloader."""

    config: JDConfig
    _enabled: bool = dataclasses.field(init=False)
    _conn: Connection | None = dataclasses.field(default=None, init=False)

    @classmethod
    def from_config(cls, config: Config, /) -> Self:
        download_dir = config.jdownloader.download_folder or config.download_folder
        return cls(
            JDConfig(
                enabled=config.jdownloader.enabled,
                device_name=config.auth.jdownloader.device_name,
                email=config.auth.jdownloader.email,
                password=config.auth.jdownloader.password,
                download_dir=download_dir.resolve(),
                autostart=config.jdownloader.autostart,
                whitelist=tuple(config.jdownloader.whitelist),
                deprecated_api=JDDeprecatedAPI.from_url(url) if (url := config.jdownloader.deprecated_api) else None,
            )
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def __post_init__(self) -> None:
        self._enabled = self.config.enabled

    def is_enabled_for(self, url: AbsoluteHttpURL) -> bool:
        if not self.enabled:
            return False
        if not self.config.whitelist:
            return True

        return any(domain in url.host for domain in self.config.whitelist)

    async def connect(self, client: HTTPClient) -> None:
        if not self.enabled or self._conn:
            return
        try:
            self._conn = await connect(client, self.config)
            version = await self._conn.jd_version()
        except Exception:
            self._enabled = False
            raise
        else:
            logger.debug("Connected to JDownloader instance version %s", version)

    async def send(self, url: AbsoluteHttpURL, title: str, download_path: Path | None = None) -> None:
        """Sends links to JDownloader."""

        assert self.enabled
        assert self._conn
        download_folder = self.config.download_dir
        if download_path:
            download_folder /= download_path

        job_id = await self._conn.add_links(
            AddLinksQuery(
                autostart=self.config.autostart,
                links=str(url),
                packageName=title or "Cyberdrop-DL",
                destinationFolder=str(download_folder),
                overwritePackagizerRules=True,
            )
        )
        logger.debug("New JDownloader job [id=%s] for %s", job_id, url)
