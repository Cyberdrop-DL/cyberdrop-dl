from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict, override

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import dates
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterable, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


class PinterestCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Pin": "/pin/<pin_id>"}
    DOMAIN: ClassVar[str] = "pinterest"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.pinterest.com")

    def __post_init__(self) -> None:
        self.api: PinterestAPI = PinterestAPI.from_crawler(self)

    @override
    async def __async_post_init__(self) -> None:
        if csrf_token := self.cookies.get("csrftoken"):
            self.api.csrf_token = csrf_token
            return

        self.log.warning("No cookies provided. Trying to get CSRF token from website")
        with self.catch_errors(self.PRIMARY_URL), self.disable_on_error("Unable to get CSRF token"):
            _ = await self.request_text(self.PRIMARY_URL, impersonate="firefox", headers=self.api.HEADERS)
            self.api.csrf_token = self.cookies["csrftoken"]

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["pin", pin_id]:
                return await self.pin(scrape_item, pin_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def pin(self, scrape_item: ScrapeItem, pin_id: str) -> None:
        pin = await self.api.pin(pin_id)
        scrape_item.setup_as_album(self.create_title(pin_id))
        scrape_item.upload_date = dates.parse_http(pin["created_at"])
        for media_dict in _media_from_pin(pin):
            media = Media(media_dict["id"], self.parse_url(media_dict["url"]))
            self.create_task(self._media(scrape_item, media))
            scrape_item.add_children()

    async def _media(self, scrape_item: ScrapeItem, media: Media) -> None:
        with self.catch_errors(media.url):
            if media.url.suffix == ".m3u8":
                return await self._m3u8_media(scrape_item, media)

            filename, ext = self.get_filename_and_ext(media.url.name)
            await self.handle_file(media.url, scrape_item, filename, ext)

    async def _m3u8_media(self, scrape_item: ScrapeItem, media: Media) -> None:
        m3u8, info = await self.request_m3u8_playlist(media.url)
        filename = self.create_custom_filename(
            media.url.name.removesuffix(".m3u8"),
            ext := ".mp4",
            resolution=info.resolution,
            video_codec=info.codecs.video,
        )
        await self.handle_file(media.url, scrape_item, filename, ext, m3u8=m3u8)


@dataclasses.dataclass(slots=True, order=True)
class Media:
    id: str
    url: AbsoluteHttpURL


class MediaDict(TypedDict):
    id: str
    url: str


class PinterestAPI(API):
    HEADERS: ClassVar[Mapping[str, str]] = {
        "Accept": "application/json, text/javascript, */*, q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "X-APP-VERSION": "1df0da9",
        "X-Pinterest-AppState": "background",
        "X-Pinterest-Source-Url": "",
        "X-Pinterest-PWS-Handler": "www/[username]/[slug].js",
        "Sec-GPC": "1",
        "Alt-Used": "www.pinterest.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    csrf_token: str

    async def pin(self, pin_id: str) -> dict[str, Any]:
        # "detailed" returns "original" entry for images
        options = {"id": pin_id, "field_set_key": "detailed"}
        data = await self.get_resource("Pin", options)
        return data["resource_response"]["data"]

    async def get_resource(self, resource: str, options: dict[str, Any]) -> dict[str, Any]:
        url = self.PRIMARY_URL / f"resource/{resource}Resource/get/"
        return await self.request_json(
            url,
            "POST",
            json={
                "data": {"options": options},
                "source_url": "",
            },
            headers={**self.HEADERS, "X-CSRFToken": self.csrf_token},
            cookies={"csrftoken": self.csrf_token},
        )

    async def pager(self, resource: str, options: dict[str, Any]) -> AsyncGenerator[dict[str, Any]]:
        end_sentinel = "Y2JOb25lO"  # b64encode('cbNone')
        while True:
            resp = await self.get_resource(resource, options)
            data = resp["resource_response"]["data"]
            yield data

            try:
                bookmarks = resp["resource"]["options"]["bookmarks"]
            except KeyError:
                break

            if not bookmarks or bookmarks[0] == "-end-" or bookmarks[0].startswith(end_sentinel):
                break
            options["bookmarks"] = bookmarks


def _media_from_story(story: dict[str, Any]) -> Generator[MediaDict]:
    for page in story["pages"]:
        block: dict[str, Any]
        for block in page["blocks"]:
            match block["type"]:
                case "story_pin_image_block":
                    yield _parse_image(block)

                case "story_pin_video_block":
                    yield _parse_video(block)

                case "story_pin_music_block":
                    yield _parse_audio(block)

                case "story_pin_product_sticker_block" | "story_pin_static_sticker_block" | "story_pin_paragraph_block":
                    continue

                case block_type:
                    raise ValueError(f"Unknown {block_type = }")


def _media_from_pin(pin: dict[str, Any]) -> Iterable[MediaDict]:
    if story := pin["story_pin_data"]:
        return _media_from_story(story)

    if video := pin.get("videos"):
        return (_parse_video({"video": video}),)

    raise ValueError("Unable to extract file data from PIN")


def _parse_audio(block: dict[str, Any]) -> MediaDict:
    audio = block["audio"]
    return {"id": audio["id"], "url": audio["audio_url"]}


def _parse_image(block: dict[str, Any]) -> MediaDict:
    return {"url": block["image"]["images"]["originals"]["url"], "id": block["image_signature"]}


def _parse_video(block: dict[str, Any]) -> MediaDict:
    video = block["video"]

    def score(fmt: tuple[str, dict[str, Any]]) -> tuple[int, int]:
        name, stream = fmt
        try:
            hls_score = ("V_HLSV3_MOBILE", "V_HLSV3_WEB", "V_HLSV4").index(name)
        except ValueError:
            hls_score = -1

        return hls_score, stream.get("width", 0)

    _, best_stream = max(video["video_list"].items(), key=score)
    return {"id": video["id"], "url": best_stream["url"]}
