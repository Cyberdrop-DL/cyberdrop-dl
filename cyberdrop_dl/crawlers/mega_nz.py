"""Crawler to download files and folders from mega.nz

This crawler does several CPU intensive operations

It calls checks_complete_by_referer several times even if no request is going to be made, to skip unnecessary compute time
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from mega.api import MegaAPI
from mega.core import MegaCore
from mega.crypto import b64_to_a32
from mega.data_structures import Crypto
from typing_extensions import override

from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths, auto_task_id
from cyberdrop_dl.downloader.mega_nz import MegaDownloader
from cyberdrop_dl.exceptions import LoginError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from mega.filesystem import FileSystem

    from cyberdrop_dl.url_objects import ScrapeItem


class MegaNzCrawler(Crawler, db_path="path_qs_frag"):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "mega.io", "mega.nz"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/file/<file_id>#<share_key>",
            "/folder/<folder_id>#<share_key>/file/<file_id>",
            "/!#<file_id>!<share_key>",
        ),
        "Folder": (
            "/folder/<folder_id>#<share_key>",
            "/F!#<folder_id>!<share_key>",
        ),
        "Subfolder": "/folder/<folder_id>#<share_key>/folder/<subfolder_id>",
        "**NOTE**": "Downloads can not be resumed. Partial downloads will always be deleted and new downloads will start over",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://mega.nz")
    ALLOW_EMPTY_PATH: ClassVar[bool] = True
    DOMAIN: ClassVar[str] = "mega.nz"
    FOLDER_DOMAIN: ClassVar[str] = "MegaNz"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("mega.co.nz",)

    core: MegaCore
    downloader: MegaDownloader

    @property
    def user(self) -> str | None:
        return self.manager.config.auth.meganz.email or None

    @property
    def password(self) -> str | None:
        return self.manager.config.auth.meganz.password or None

    @override
    def __init_downloader__(self) -> None:
        api = MegaAPI(self.manager.client_manager._session)
        api.user_agent = CDL_USER_AGENT
        self.core = MegaCore(api)
        self.downloader = dl = MegaDownloader(self.manager, self.DOMAIN)  # type: ignore[reportIncompatibleVariableOverride]
        dl.startup()

    async def __async_post_init__(self) -> None:
        await self.login(self.PRIMARY_URL)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if not self._logged_in:
            return

        info = self.core.parse_url(scrape_item.url)
        if not info.is_folder:
            return await self.file(scrape_item, info.public_handle, info.public_key)

        await self.folder(scrape_item, info.public_handle, info.public_key, info.selected_folder, info.selected_file)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, handle: str, public_key: str) -> None:
        canonical_url = (self.PRIMARY_URL / "file" / handle).with_fragment(public_key)
        if await self.check_complete_from_referer(canonical_url):
            return

        scrape_item.url = canonical_url
        full_key = b64_to_a32(public_key)
        await self._process_file(scrape_item, handle, Crypto.decompose(full_key))

    @error_handling_wrapper
    async def _process_file(
        self,
        scrape_item: ScrapeItem,
        handle: str,
        crypto: Crypto,
        *,
        folder_id: str | None = None,
    ) -> None:
        resp = await self.core.request_file_info(handle, folder_id, is_public=not folder_id)
        if not resp.url:
            raise ScrapeError(410, "File not accessible anymore")

        name = self.core.decrypt_attrs(resp._at, crypto.key, handle).name
        self.downloader.register(scrape_item.url, crypto, resp.size)
        file_url = self.parse_url(resp.url)
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(scrape_item.url, scrape_item, filename, ext, debrid_link=file_url)

    _process_file_task = auto_task_id(_process_file)

    @error_handling_wrapper
    async def folder(
        self,
        scrape_item: ScrapeItem,
        handle: str,
        public_key: str,
        root_id: str | None = None,
        single_file_id: str | None = None,
    ) -> None:
        if single_file_id and await self.check_complete_from_referer(scrape_item.url):
            return

        selected_node = root_id or single_file_id
        fs = await self.core.get_public_filesystem(handle, public_key)
        root = next(iter(fs))
        title = self.create_title(root.attributes.name, handle)
        scrape_item.setup_as_album(title, album_id=handle)
        canonical_url = (self.PRIMARY_URL / "folder" / handle).with_fragment(public_key)
        scrape_item.url = canonical_url
        await self._process_fs(scrape_item, fs, selected_node)

    async def _process_fs(self, scrape_item: ScrapeItem, filesystem: FileSystem, selected_node_id: str | None) -> None:
        folder_id, public_key = scrape_item.url.name, scrape_item.url.fragment

        for file in filesystem.files_from(selected_node_id):
            path = filesystem.relative_path(file.id)
            file_fragment = f"{public_key}/file/{file.id}"
            canonical_url = scrape_item.url.with_fragment(file_fragment)
            if await self.check_complete_from_referer(canonical_url):
                continue

            child_item = scrape_item.create_child(canonical_url, possible_datetime=file.created_at)
            for part in path.parent.parts[1:]:
                child_item.add_to_parent_title(part)

            self.create_task(self._process_file_task(child_item, file.id, file._crypto, folder_id=folder_id))
            scrape_item.add_children()

    @error_handling_wrapper
    async def login(self, *_) -> None:
        # This takes a really long time (dozens of seconds)
        # TODO: Add a way to cache this login
        # TODO: Show some logging message / UI about login
        try:
            await self.core.login(self.user, self.password)
            self._logged_in = True
        except Exception as e:
            self.disabled = True
            raise LoginError(f"[MegaNZ] {e}") from e
