from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, NotRequired, TypedDict

from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem

_API_ENTRYPOINT = AbsoluteHttpURL("https://a.4cdn.org/")
_FILES_BASE_URL = AbsoluteHttpURL("https://i.4cdn.org/")


class ImagePost(TypedDict):
    filename: str  # File stem
    ext: str
    tim: int  # Unix timestamp + microtime of uploaded image
    sub: NotRequired[str]  # Subject
    com: NotRequired[str]  # Comment
    time: int  # Unix timestamp


class FourChanCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Board": "/<board>",
        "Thread": "/<board>/thread/<thread_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://boards.4chan.org")
    DOMAIN: ClassVar[str] = "4chan"
    _DOWNLOAD_SLOTS: ClassVar[int | None] = 1
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 10

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [board, "thread", thread_id, *_]:
                return await self.thread(scrape_item, board, thread_id)
            case [board]:
                return await self.board(scrape_item, board)
            case [board, _]:
                return await self.board(scrape_item, board)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def thread(self, scrape_item: ScrapeItem, board: str, thread_id: str) -> None:
        api_url = _API_ENTRYPOINT / board / f"thread/{thread_id}.json"
        response: dict[str, list[ImagePost]] = await self.request_json(api_url)
        if not response:
            raise ScrapeError(404)

        original_post = response["posts"][0]
        if subject := original_post.get("sub"):
            title: str = subject
        elif comment := original_post.get("com"):
            title = BeautifulSoup(comment).get_text(strip=True)
        else:
            title = f"#{thread_id}"

        title = self.create_title(f"{title} [thread]", thread_id)
        scrape_item.setup_as_album(title, album_id=thread_id)
        results = await self.get_album_results(thread_id)

        for post in response["posts"]:
            file_stem = post.get("filename")
            if not file_stem:
                continue

            file_micro_timestamp, ext = post["tim"], post["ext"]
            url = _FILES_BASE_URL / board / f"{file_micro_timestamp}{ext}"
            if self.check_album_results(url, results):
                continue

            custom_filename = self.create_custom_filename(file_stem, ext)
            filename, _ = self.get_filename_and_ext(url.name)
            new_scrape_item = scrape_item.copy()
            new_scrape_item.uploaded_at = post["time"]
            await self.handle_file(
                url,
                new_scrape_item,
                filename,
                ext,
                custom_filename=custom_filename,
                metadata=post,
            )
            scrape_item.add_children()

    @error_handling_wrapper
    async def board(self, scrape_item: ScrapeItem, board: str) -> None:
        api_url: AbsoluteHttpURL = _API_ENTRYPOINT / board / "threads.json"
        threads: list[dict[str, Any]] = await self.request_json(api_url)
        scrape_item.setup_as_forum("")
        for page in threads:
            for thread in page["threads"]:
                url = self.PRIMARY_URL / board / f"thread/{thread['no']}"
                new_scrape_item = scrape_item.create_child(url)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()
