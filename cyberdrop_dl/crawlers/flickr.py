from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


_API_ENDPOINT = AbsoluteHttpURL("https://api.flickr.com/services/rest")


class FlickrCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Photo": ("/photo/<user_nsid>/<photo_id>/..."),
    }

    DOMAIN: ClassVar[str] = "flickr"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.flickr.com")
    API_KEY = "6cf8d4d0f4c6fe9e2c57e510920d810b"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["photos", _, photo_id, *_]:
                return await self.photo(scrape_item, photo_id)

            case _:
                raise ValueError

    async def _api_request(self, method: str, **params: Any) -> dict[str, Any]:
        api_url = _API_ENDPOINT.with_query(
            method="flickr." + method,
            format="json",
            nojsoncallback=1,
            api_key=self.API_KEY,
        )
        if params:
            api_url = api_url.update_query(params)
        return await self.request_json(api_url)

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem, photo_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        photo = (await self._api_request("photos.getInfo", photo_id=photo_id))["photo"]
        name: str = photo["title"]["_content"]
        scrape_item.possible_datetime = int(photo["dateuploaded"])
        source = await self._get_source_url(photo_id)
        filename, ext = self.get_filename_and_ext(name + source.suffix)
        await self.handle_file(
            source,
            scrape_item,
            name,
            ext,
            custom_filename=filename,
            metadata=photo,
        )

    async def _get_source_url(self, photo_id: str) -> AbsoluteHttpURL:
        sizes: list[dict[str, str]] = (
            await self._api_request(
                "photos.getSizes",
                photo_id=photo_id,
            )
        )["sizes"]["size"]
        best = sizes[-1]["source"]
        return self.parse_url(best)
