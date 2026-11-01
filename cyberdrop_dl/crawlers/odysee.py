from __future__ import annotations

import dataclasses
import time
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import NoExtensionError, ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("url")
class OdyseeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": ("/@channel:uri",),
        "Embed": ("/$/embed/@channel:uri",),
    }

    DOMAIN: ClassVar[str] = "odysee"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://odysee.com")

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        return url.with_path(url.path.removeprefix("/$/embed"), keep_query=True)

    def __post_init__(self) -> None:
        self.api: LBRYAPI = LBRYAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [channel, _] if channel.startswith("@"):
                uri = "lbry:/" + scrape_item.url.path.replace(":", "#")
                await self.video(scrape_item, uri)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, uri: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.resolve(uri)
        src = await self.api.stream(uri, scrape_item.url.query)
        filename = self.create_custom_filename(
            video.title,
            ext := ".mp4",
            file_id=video.id,
            resolution=Resolution(video.width, video.height),
        )
        scrape_item.uploaded_at = video.release_time
        await self.handle_file(
            AbsoluteHttpURL(uri),
            scrape_item,
            video.title,
            ext,
            custom_filename=filename,
            debrid_link=src,
            metadata=video,
            thumbnail=video.thumbnail,
        )

    @override
    @classmethod
    def get_filename_and_ext(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        filename: str,
        *,
        assume_ext: str | None = ".mp4",
        mime_type: str | None = None,
    ) -> tuple[str, str]:
        try:
            return super().get_filename_and_ext(filename, mime_type=mime_type, assume_ext=assume_ext)
        except NoExtensionError:
            return super().get_filename_and_ext(filename + ".webp", mime_type=mime_type, assume_ext=assume_ext)


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: str
    title: str
    height: int
    width: int
    release_time: int
    thumbnail: AbsoluteHttpURL

    @classmethod
    def parse(cls, stream: dict[str, Any]) -> Self:
        video = stream["value"] | stream["value"]["video"]
        return deserialize(
            cls,
            video,
            id=stream["claim_id"],
            thumbnail=parse_http_url(video["thumbnail"]["url"]),
            release_time=int(video["release_time"]),
        )


class LBRYAPI(API):
    PROXY: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.na-backend.odysee.com/api/v1/proxy")

    async def request_json_rpc(self, method: str, **params: Any) -> dict[str, Any]:
        resp = await self.request_json(
            self.PROXY,
            headers={"Content-Type": "application/json-rpc"},
            json={
                "id": int(time.time()),
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            },
        )

        if error := resp.get("error"):
            msg = f"{error.get('code')} - {error.get('message')}"
            raise ScrapeError(422, msg)

        return resp["result"]

    async def resolve(self, url: str) -> Video:
        resp = await self.request_json_rpc("resolve", urls=url)
        stream = resp[url]
        if error := stream.get("error"):
            code = 404 if error.get("name") == "NOT_FOUND" else 422
            raise ScrapeError(code, error.get("text") or str(error))

        stream_type = stream["value"].get("stream_type", "livestream")
        if stream_type != "video":
            raise ScrapeError(422, f"{stream_type = } is not supported")
        return Video.parse(stream)

    async def stream(self, url: str, query: Mapping[str, str]) -> AbsoluteHttpURL:
        signature = {name: value for name in ("signature", "signature_ts") if (value := query.get(name))}
        resp = await self.request_json_rpc(
            "get",
            enviroment=None,
            uri=url,
            **signature,
        )
        stream_url = parse_http_url(resp["streaming_url"])
        if stream_url.suffix == ".m3u8":
            raise ValueError("Unsupport m3u8 stream")
        return stream_url
