from __future__ import annotations

from typing import TYPE_CHECKING

from cyberdrop_dl.constants import FILE_FORMATS
from cyberdrop_dl.data_structures.url_objects import MediaItem
from cyberdrop_dl.downloader.downloader import Downloader
from cyberdrop_dl.exceptions import NoExtensionError
from cyberdrop_dl.utils.logger import log
from cyberdrop_dl.utils.utilities import get_download_path, get_filename_and_ext

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem
    from cyberdrop_dl.managers.manager import Manager


from typing import Final

MEDIA_EXTENSIONS = FILE_FORMATS["Images"] | FILE_FORMATS["Videos"] | FILE_FORMATS["Audio"]


class DirectHttpFile:
    DOMAIN: Final = "no_crawler"

    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        self.downloader = Downloader(manager, self.DOMAIN)

    def startup(self) -> None:
        self.downloader.startup()

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        """Checks if the URL has a valid extension."""

        try:
            filename, ext = get_filename_and_ext(scrape_item.url.name)
        except NoExtensionError:
            filename, ext = get_filename_and_ext(scrape_item.url.name, forum=True)

        if ext in MEDIA_EXTENSIONS:
            raise ValueError

        if await self.skip_no_crawler_by_config(scrape_item):
            return

        scrape_item.add_to_parent_title("Loose Files")
        scrape_item.part_of_album = True
        download_folder = get_download_path(self.manager, scrape_item, self.DOMAIN)

        media_item = MediaItem.from_item(
            scrape_item,
            scrape_item.url,
            self.DOMAIN,
            download_folder,
            filename,
            original_filename=scrape_item.url.name,
        )
        self.manager.task_group.create_task(self.downloader.run(media_item))

    async def skip_no_crawler_by_config(self, scrape_item: ScrapeItem) -> bool:
        check_complete = await self.manager.db_manager.history_table.check_complete(
            "no_crawler",
            scrape_item.url,
            scrape_item.url,
        )
        if check_complete:
            log(f"Skipping {scrape_item.url} as it has already been downloaded", 10)
            self.manager.progress_manager.download_progress.add_previously_completed()
            return True

        posible_referer = scrape_item.parents[-1] if scrape_item.parents else scrape_item.url
        check_referer = False
        if self.manager.config_manager.settings_data.download_options.skip_referer_seen_before:
            check_referer = await self.manager.db_manager.temp_referer_table.check_referer(posible_referer)

        if check_referer:
            log(f"Skipping {scrape_item.url} as referer has been seen before", 10)
            self.manager.progress_manager.download_progress.add_skipped()
            return True

        return False
