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

    from cyberdrop_dl.config import Config
    from cyberdrop_dl.url_objects import AbsoluteHttpURL


@dataclasses.dataclass(frozen=True, slots=True)
class JDConfig:
    enabled: bool
    username: str | None
    password: str | None
    device: str | None
    download_dir: Path
    autostart: bool
    whitelist: tuple[str, ...]


@dataclasses.dataclass(slots=True)
class JDownloader:
    """Class that handles connecting and sending links to JDownloader."""

    config: JDConfig
    _enabled: bool = dataclasses.field(init=False)
    _device: Jddevice | None = dataclasses.field(default=None, init=False)

    @classmethod
    def from_config(cls, config: Config, /) -> Self:
        download_dir = config.jdownloader.download_folder or config.download_folder
        return cls(
            JDConfig(
                enabled=config.jdownloader.enabled,
                device=config.auth.jdownloader.device,
                username=config.auth.jdownloader.username,
                password=config.auth.jdownloader.password,
                download_dir=download_dir.resolve(),
                autostart=config.jdownloader.autostart,
                whitelist=tuple(config.jdownloader.whitelist),
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

        assert self._device is not None
        assert self.enabled
        with self._wrap_errors():
            download_folder = self.config.download_dir
            if download_path:
                download_folder /= download_path

            await asyncio.to_thread(
                self._device.linkgrabber.add_links,
                [
                    {
                        "autostart": self.config.autostart,
                        "links": str(url),
                        "packageName": title or "Cyberdrop-DL",
                        "destinationFolder": str(download_folder),
                        "overwritePackagizerRules": True,
                    },
                ],
            )
