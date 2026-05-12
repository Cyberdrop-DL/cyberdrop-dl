from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from mega.transfer_it import TransferItClient

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from mega import Node
    from mega.filesystem import FileSystem

    from cyberdrop_dl.url_objects import ScrapeItem


class TransferItCrawler(Crawler, db_path="path_qs_frag"):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Transfer": "/t/<transfer_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://transfer.it")
    DOMAIN: ClassVar[str] = "transfer.it"

    core: TransferItClient

    async def __async_post_init__(self) -> None:
        self.core = TransferItClient(self.manager.http_client._session)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["t", transfer_id]:
                return await self.transfer(scrape_item, transfer_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def transfer(self, scrape_item: ScrapeItem, transfer_id: str) -> None:
        # TODO: handle expired links and password protected links
        fs = await self.core.get_filesystem(transfer_id)
        root = next(iter(fs))
        title = self.create_title(root.attributes.name, transfer_id)
        scrape_item.setup_as_album(title, album_id=transfer_id)
        self._process_filesystem(scrape_item, fs, transfer_id)

    def _process_filesystem(self, scrape_item: ScrapeItem, fs: FileSystem, transfer_id: str) -> None:
        password = scrape_item.url.query.get("pw") or scrape_item.password

        for file in fs.files:
            path = fs.relative_path(file.id)
            canonical_url = scrape_item.url.with_fragment(file.id)
            new_scrape_item = scrape_item.create_child(canonical_url)
            for part in path.parent.parts[1:]:
                new_scrape_item.add_to_parent_title(part)

            dl_link = self.core.create_download_url(transfer_id, file, password)
            self.create_task(self._file(new_scrape_item, file, dl_link))
            scrape_item.add_children()

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: Node, dl_link: str) -> None:
        link = self.parse_url(dl_link)
        filename, ext = self.get_filename_and_ext(file.attributes.name)
        scrape_item.uploaded_at = file.created_at
        await self.handle_file(link, scrape_item, file.attributes.name, ext, custom_filename=filename)
