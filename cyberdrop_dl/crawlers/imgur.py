from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

_API_ENTRYPOINT = AbsoluteHttpURL("https://api.imgur.com/3/")
_IMAGE_CDN = AbsoluteHttpURL("https://i.imgur.com")


class ImgurCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Gallery": "/gallery/<slug>-<album_id>",
        "Image": "/<image_id>",
        "Direct links": f"{_IMAGE_CDN}/<image_id>.<ext>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://imgur.com/")
    DOMAIN: ClassVar[str] = "imgur"

    def __post_init__(self) -> None:
        self.client_id: str = ""

    @classmethod
    def _json_response_check(cls, json_resp: dict[str, Any]) -> None:
        if data := json_resp.get("data"):
            raise ScrapeError(json_resp["status"], data["error"])

    async def async_startup(self) -> None:
        await self._get_client_id(self.PRIMARY_URL)

    # TODO: cache this
    @error_handling_wrapper
    async def _get_client_id(self, _) -> None:
        """Get public client id."""
        with self.disable_on_error("Unable to get client id"):
            soup = await self.request_soup(self.PRIMARY_URL)
            js_src = css.select_one_get_attr(soup, "script[src*='/desktop-assets/js/main']", "src")
            js_text = await self.request_text(self.parse_url(js_src))
            self.client_id = get_text_between(js_text, 'apiClientId:"', '"')

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.host == _IMAGE_CDN.host:
            return await self.direct_file(scrape_item)

        match scrape_item.url.parts[1:]:
            case ["a", album_id]:
                return await self.album(scrape_item, album_id)
            case [slug]:
                image_id = slug.partition(".")[0]
                return await self.image(scrape_item, image_id)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        match url.parts[1:]:
            case ["gallery", slug]:
                album_id = slug.rpartition("-")[-1]
                return cls.PRIMARY_URL / "a" / album_id
            case _:
                return url

    async def _api_request(self, *parts: str) -> dict[str, str]:
        api_url = _API_ENTRYPOINT.joinpath(*parts)
        return (
            await self.request_json(
                api_url,
                headers={"Authorization": f"Client-ID {self.client_id}"},
            )
        )["data"]

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        album: dict[str, Any] = await self._api_request("album", album_id)
        title = self.create_title(album.get("title") or album_id, album_id=album_id)
        scrape_item.setup_as_album(title, album_id=album_id)
        results = await self.get_album_results(album_id)
        for image in album["images"]:
            link = self.parse_url(image["link"])
            if self.check_album_results(link, results):
                continue
            web_url = self.PRIMARY_URL / image["id"]
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self._image(new_scrape_item, image))
            scrape_item.add_children()

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem, image_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        image = await self._api_request("image", image_id)
        await self._image(scrape_item, image)

    @error_handling_wrapper
    async def _image(self, scrape_item: ScrapeItem, image: dict[str, Any]) -> None:
        scrape_item.possible_datetime = image["datetime"]
        url = self.parse_url(image["link"])
        filename, ext = self.get_filename_and_ext(url.name)
        await self.handle_file(url, scrape_item, filename, ext, metadata=image)
