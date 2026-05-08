from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, final

from mega.chunker import MegaChunker, get_chunks
from typing_extensions import override

from cyberdrop_dl import aio, storage
from cyberdrop_dl.clients.download_client import DownloadClient, make_speed_checker
from cyberdrop_dl.downloader.http import Downloader

if TYPE_CHECKING:
    import aiohttp
    from mega.data_structures import Crypto
    from yarl import URL

    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.progress import ProgressHook
    from cyberdrop_dl.url_objects import MediaItem


@final
class MegaDownloadClient(DownloadClient):
    def __init__(self, manager: Manager) -> None:
        super().__init__(manager, manager.http_client)
        self._decrypt_mapping: dict[URL, tuple[Crypto, int]] = {}
        self._supports_ranges = False

    async def _append_content(self, media_item: MediaItem, hook: ProgressHook, content: aiohttp.StreamReader) -> None:
        """Appends content to a file."""

        check_free_space = storage.create_free_space_checker(media_item)
        check_download_speed = make_speed_checker(media_item, hook, self.download_speed_threshold)
        await check_free_space()
        await self._pre_download_check(media_item)

        crypto, file_size = self._decrypt_mapping.pop(media_item.url)
        chunk_decryptor = MegaChunker(crypto.key, crypto.iv, crypto.meta_mac)

        async with aio.open(media_item.partial_file, mode="ab") as f:
            for _, chunk_size in get_chunks(file_size):
                raw_chunk = await content.readexactly(chunk_size)
                chunk = chunk_decryptor.read(raw_chunk)
                await check_free_space()
                chunk_size = len(chunk)

                await self.client.speed_limiter.acquire(chunk_size)
                await f.write(chunk)
                hook.advance(chunk_size)
                check_download_speed()

        await self._post_download_check(media_item)
        chunk_decryptor.check_integrity()

    @aio.to_thread
    def _pre_download_check(self, media_item: MediaItem) -> None:
        media_item.partial_file.parent.mkdir(parents=True, exist_ok=True)
        media_item.partial_file.unlink(missing_ok=True)  # We can't resume
        media_item.partial_file.touch()


@dataclasses.dataclass(slots=True)
class MegaDownloader(Downloader):
    _client: MegaDownloadClient = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        super(MegaDownloader, self).__post_init__()
        self._client = MegaDownloadClient(self.manager)

    @override
    @property
    def client(self) -> MegaDownloadClient:
        return self._client

    @property
    def max_attempts(self):
        return 1

    def register(self, url: URL, crypto: Crypto, file_size: int) -> None:
        self.client._decrypt_mapping[url] = crypto, file_size
