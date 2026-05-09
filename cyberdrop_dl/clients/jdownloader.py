from __future__ import annotations

import asyncio
import contextlib
import dataclasses
from typing import TYPE_CHECKING, Self

from myjdapi import myjdapi

from cyberdrop_dl.exceptions import JDownloaderError

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from myjdapi.myjdapi import Jddevice

    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL


@dataclasses.dataclass(frozen=True, slots=True)
class Config:
    enabled: bool
    username: str
    password: str
    device: str
    download_dir: Path
    autostart: bool
    whitelist: tuple[str, ...]

    @staticmethod
    def from_manager(manager: Manager) -> Config:
        download_dir = (
            manager.config.settings.runtime_options.jdownloader_download_dir
            or manager.config.settings.files.download_folder
        )
        return Config(
            enabled=manager.config.settings.runtime_options.send_unsupported_to_jdownloader,
            device=manager.config.auth.jdownloader.device,
            username=manager.config.auth.jdownloader.username,
            password=manager.config.auth.jdownloader.password,
            download_dir=download_dir.resolve(),
            autostart=manager.config.settings.runtime_options.jdownloader_autostart,
            whitelist=tuple(manager.config.settings.runtime_options.jdownloader_whitelist),
        )


@dataclasses.dataclass(slots=True)
class JDownloader:
    """Class that handles connecting and sending links to JDownloader."""

    config: Config
    _enabled: bool = dataclasses.field(init=False)
    _device: Jddevice | None = dataclasses.field(default=None, init=False)

    @classmethod
    def from_manager(cls, manager: Manager, /) -> Self:
        return cls(Config.from_manager(manager))

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

    @contextlib.contextmanager
    def _wrap_errors(self) -> Generator[None]:
        try:
            yield
        except myjdapi.MYJDDeviceNotFoundException:
            raise JDownloaderError(f"Device not found ({self.config.device})") from None
        except myjdapi.MYJDApiException as e:
            raise JDownloaderError(str(e)) from e

    async def _connect(self) -> None:
        if not self._enabled or self._device is not None:
            return

        if not all((self.config.username, self.config.password, self.config.device)):
            raise JDownloaderError("JDownloader credentials were not provided")

        with self._wrap_errors():
            api = myjdapi.Myjdapi()
            api.set_app_key("CYBERDROP-DL")
            _ = await asyncio.to_thread(api.connect, self.config.username, self.config.password)
            self._device = api.get_device(self.config.device)

    async def connect(self) -> None:
        try:
            return await self._connect()
        except Exception:
            self._enabled = False
            raise

    async def send(self, url: AbsoluteHttpURL, title: str, download_path: Path | None = None) -> None:
        """Sends links to JDownloader."""

        assert self._device is not None and self.enabled
        with self._wrap_errors():
            download_folder = self.config.download_dir
            if download_path:
                download_folder = download_folder / download_path

            await asyncio.to_thread(
                self._device.linkgrabber.add_links,
                [
                    {
                        "autostart": self.config.autostart,
                        "links": str(url),
                        "packageName": title if title else "Cyberdrop-DL",
                        "destinationFolder": str(download_folder),
                        "overwritePackagizerRules": True,
                    },
                ],
            )
