from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils import dates

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class GoonboxCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<id>",
        "Image": "/img/<id>",
        "Direct links": "/api/<type>/<id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://goonbox.cr")
    DOMAIN: ClassVar[str] = "goonbox.cr"
    FOLDER_DOMAIN: ClassVar[str] = "GoonBox"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", album_id]:
                return await self.album(scrape_item, album_id)
            case ["img", image_id]:
                return await self.image(scrape_item, image_id)
            case ["api", "albums", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["api", "images", image_id, *_]:
                return await self.image(scrape_item, image_id)
            case _:
                raise ValueError

    @override
    async def __async_post_init__(self) -> None:
        self.api: GoonboxAPI = GoonboxAPI.from_crawler(self)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        title = ""
        page = 1
        async for album_title, images in self.api.album_pages(album_id):
            if not title:
                title = self.create_title(album_title, album_id=album_id)
                scrape_item.setup_as_album(title, album_id=album_id)
            for image in images:
                new_scrape_item = scrape_item.create_child(image.web_url)
                new_scrape_item.uploaded_at = image.uploaded_at
                self.create_task(self.direct_file(new_scrape_item, image.original_url))
                scrape_item.add_children()
            page += 1

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem, image_id: str) -> None:
        image = await self.api.image(image_id)
        scrape_item.uploaded_at = image.uploaded_at
        await self.direct_file(scrape_item, image.original_url)


class _Image:
    __slots__ = ("original_url", "web_url", "uploaded_at")

    def __init__(self, data: dict[str, Any], primary_url: AbsoluteHttpURL, parse_url: Any) -> None:
        self.original_url: AbsoluteHttpURL = parse_url(data["original_url"])
        self.web_url: AbsoluteHttpURL = primary_url / "img" / data["encoded_id"]
        self.uploaded_at: float = dates.parse_iso(data["created_at"]).timestamp()


class GoonboxAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://goonbox.cr/api")

    async def image(self, image_id: str) -> _Image:
        api_url = self.ENTRYPOINT / "images" / image_id
        resp = await self.request_json(api_url)
        return _Image(resp["image"], self.PRIMARY_URL, self.parse_url)

    async def album_pages(self, album_id: str) -> AsyncGenerator[tuple[str, list[_Image]]]:
        page = 1
        while True:
            api_url = (self.ENTRYPOINT / "albums" / album_id).with_query(page=page)
            resp = await self.request_json(api_url)
            album = resp["album"]
            images = [_Image(img, self.PRIMARY_URL, self.parse_url) for img in resp["images"]]
            if not images:
                return
            yield album["title"], images

            pagination = resp.get("pagination") or {}
            current_page = pagination.get("current_page", page)
            last_page = pagination.get("last_page", page)
            if current_page >= last_page:
                return
            page += 1
