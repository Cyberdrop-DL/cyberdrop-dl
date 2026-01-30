from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.mediaprops import Resolution
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_context, error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class FlickrCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Photo": "/photos/<user_nsid>/<photo_id>/...",
        "Album": "/photos/<user_nsid>/albums/<photoset_id>/...",
    }

    DOMAIN: ClassVar[str] = "flickr"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.flickr.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["photos", user, "albums", photoset_id, *_]:
                return await self.photoset(scrape_item, user, photoset_id)
            case ["photos", user, photo_id, *_]:
                scrape_item.url = self.PRIMARY_URL / "photos" / user / photo_id
                return await self.photo(scrape_item, photo_id)
            case _:
                raise ValueError

    async def async_startup(self) -> None:
        self.api: FlickrAPI = FlickrAPI(self)
        await self.api.get_site_key()

    @error_handling_wrapper
    async def photoset(self, scrape_item: ScrapeItem, user: str, photoset_id: str) -> None:
        title: str = ""
        async for data in self.api.photoset(photoset_id):
            photos: list[dict[str, Any]] = data.pop("photo")

            if not title:
                name = data["title"]
                title = self.create_title(
                    name["_content"] if isinstance(name, dict) else name,
                    photoset_id,
                )
                scrape_item.setup_as_album(title, album_id=photoset_id)
                await self.write_metadata(scrape_item, photoset_id, data)

            for photo in photos:
                web_url = self.PRIMARY_URL / "photos" / user / photo["id"]
                new_scrape_item = scrape_item.create_child(web_url)
                self.create_task(self._photo(new_scrape_item, photo))
                scrape_item.add_children()

    async def photo(self, scrape_item: ScrapeItem, photo_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        photo = await self.api.photo(photo_id)
        await self._photo(scrape_item, photo)

    @error_handling_wrapper
    async def _photo(self, scrape_item: ScrapeItem, photo: dict[str, Any]) -> None:
        scrape_item.possible_datetime = int(photo.get("dateuploaded") or photo["dateupload"])
        title = photo["title"]
        name: str = (title["_content"] if isinstance(title, dict) else title) or photo["media"]
        source = await self._get_source(photo)
        filename = self.create_custom_filename(name, source.suffix, file_id=photo["id"])
        await self.handle_file(
            source,
            scrape_item,
            name,
            source.suffix,
            custom_filename=filename,
            metadata=photo,
        )

    async def _get_source(self, photo: dict[str, Any]) -> AbsoluteHttpURL:
        if original := photo.get("url_o"):
            return self.parse_url(original)
        if photo["media"] == "video":
            return await self.api.video_source(photo["id"], photo["secret"])
        return await self.api.photo_source(photo["id"])


class FlickrAPI:
    API_ENDPOINT = AbsoluteHttpURL("https://api.flickr.com/services/rest")

    def __init__(self, crawler: Crawler) -> None:
        self._crawler = crawler
        self.api_key: str = ""

    def __repr__(self) -> str:
        return f"{type(self).__name__}(api_key={self.api_key!r})"

    async def get_site_key(self) -> None:
        prints = self._crawler.PRIMARY_URL / "prints"
        with (
            error_handling_context(self._crawler, prints),
            self._crawler.disable_on_error("Unable to get public API key"),
        ):
            text = await self._crawler.request_text(prints)
            self.api_key = get_text_between(text, 'flickr.api.site_key = "', '"')

    async def _request(self, method: str, **params: Any) -> dict[str, Any]:
        api_url = self.API_ENDPOINT.with_query(
            method="flickr." + method,
            format="json",
            nojsoncallback=1,
            api_key=self.api_key,
        )
        if params:
            api_url = api_url.update_query(params)

        return await self._crawler.request_json(api_url)

    async def photo(self, photo_id: str) -> dict[str, Any]:
        resp = await self._request("photos.getInfo", photo_id=photo_id)
        return resp["photo"]

    async def photo_source(self, photo_id: str) -> AbsoluteHttpURL:
        resp = await self._request("photos.getSizes", photo_id=photo_id)
        best_src = resp["sizes"]["size"][-1]["source"]
        return self._crawler.parse_url(best_src)

    async def video_source(self, video_id: str, secret: str) -> AbsoluteHttpURL:
        resp = await self._request("video.getStreamInfo", photo_id=video_id, secret=secret)

        def parse_resolution(stream_name: str) -> Resolution:
            if stream_name == "orig":
                return Resolution.highest()
            try:
                return Resolution.parse(stream_name)
            except ValueError:
                return Resolution.unknown()

        streams: dict[str, str] = {s["type"]: s["_content"] for s in resp["streams"]["stream"]}
        best_src = max(streams, key=parse_resolution)
        return self._crawler.parse_url(streams[best_src])

    async def photoset(self, photoset_id: str) -> AsyncGenerator[dict[str, Any]]:
        for page in itertools.count(1):
            data = (
                await self._request(
                    "photosets.getPhotos",
                    photoset_id=photoset_id,
                    page=page,
                    extras="date_upload,media,url_o",
                )
            )["photoset"]
            yield data
            if page >= data["pages"]:
                break
