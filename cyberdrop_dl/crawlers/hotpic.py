from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, dates, next_or_error, traversal
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Iterable

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


def _random_id(length: int = 13) -> str:
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class HotPicCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/album/<album_id>",
        "Image/Video": "/i/<file-id>",
        "Reddit Image": "/ri/<image_id>",
        "Reddit Video": "/video/<video_id>",
        "Direct files": (
            "/uploads/...",
            "/reddit/...",
        ),
    }
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("hotpic", "kiwi99.space")
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://hotpic.cc")
    DOMAIN: ClassVar[str] = "hotpic"
    FOLDER_DOMAIN: ClassVar[str] = "HotPic"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "2385290.xyz", "myhostdata.space"
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cdn3.kiwi99.space")
    VIDEO_CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://videos.kiwi99.space")

    def __post_init__(self) -> None:
        self._dummy_referer: str = str(self.PRIMARY_URL / "i" / _random_id())

    @override
    def _prepare_headers(self, scrape_item: ScrapeItem) -> dict[str, str]:
        # Fix direct files referer
        headers = super()._prepare_headers(scrape_item)
        if scrape_item.url.host != self.PRIMARY_URL.host:
            headers["Referer"] = self._dummy_referer
        return headers

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["album", album_id]:
                await self.album(scrape_item, album_id)
            case ["i" | "ri", post_id]:
                await self.file(scrape_item, post_id, self.CDN)
            case ["video", post_id]:
                await self.file(scrape_item, post_id, self.VIDEO_CDN)
            case ["uploads" | "reddit" | "videos", _, *_]:
                await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        return _thumb_to_src(super().transform_url(url))

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup, completed = await aio.gather(self.request_soup(scrape_item.url), self.get_completed_by_album(album_id))

        info = _extr_json_ld(soup, "Collection")
        name = traversal.find_obj(info, validate={"@type": "Collection"})[1]["name"]
        scrape_item.setup_as_profile(self.create_title(name, album_id), album_id=album_id)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for media in _extract_media_objs(info, None):
                if media.src in completed:
                    continue

                new_item = scrape_item.create_child(self.PRIMARY_URL / "i" / media.id)
                tg.create_task(self._media(new_item, media))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, post_id: str, cdn: AbsoluteHttpURL) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        media = next_or_error(_extract_media_objs(_extr_json_ld(soup), post_id, cdn), "media")
        await self._media(scrape_item, media)

    @error_handling_wrapper
    async def _media(self, scrape_item: ScrapeItem, media: Media) -> None:
        scrape_item.uploaded_at = media.uploaded_at
        name = media.name or media.src.name
        _, ext = self.get_filename_and_ext(media.src.name)
        await self.handle_file(
            media.src,
            scrape_item,
            name,
            ext,
            thumbnail=media.thumb,
            custom_filename=self.create_custom_filename(name, ext),
        )


@struct
class Media:
    id: str
    name: str | None
    uploaded_at: int
    src: AbsoluteHttpURL
    thumb: AbsoluteHttpURL


def _extract_media_objs(
    ld_json: dict[str, Any], post_id: str | None, cdn: AbsoluteHttpURL = HotPicCrawler.CDN
) -> Iterable[Media]:
    def parse_cdn_url(url: str):
        return HotPicCrawler.parse_url(url).with_host(cdn.host)

    for otype in ("VideoObject", "ImageObject"):
        for _, obj in traversal.find_objs(ld_json, validate={"@type": otype}):
            src = parse_cdn_url(obj["contentUrl"])
            if post_id:
                media_id = post_id
                name = (obj.get("name") or "").rpartition(" by ")[0] or None
            else:
                post, _, index = Path(parse_cdn_url(obj["thumbnailUrl"]).name).stem.rpartition("T")
                assert post
                media_id = f"{post}{index}"
                name = None

            yield Media(
                id=media_id,
                name=name,
                src=src,
                uploaded_at=HotPicCrawler.parse_iso_date(obj["uploadDate"]),
                thumb=(src.parent / "thumb" / src.name).with_suffix(".webp"),
            )


def _extr_json_ld(soup: BeautifulSoup, /, contains: tuple[str, ...] | str = ()) -> Any:
    for script in css.iselect_text(soup, "script[type='application/ld+json']", contains):
        # fix malformed description
        return json.loads(script.replace("\r\n", " "))

    try:
        release_date = css.select(soup, "#exCount", "data-release")
    except css.SelectorError:
        raise ScrapeError(422, "Unable to extract json-ld data") from None

    date = dates.from_timestamp(float(release_date)).replace(tzinfo=None)
    raise ScrapeError(401, f"Locked album. It unlocks for everyone at {date} UTC")


def _thumb_to_src(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    match url.parts[1:]:
        case ["uploads" | "reddit", _, *_]:
            url = url.with_host(HotPicCrawler.CDN.host)
        case ["videos", _, *_]:
            url = url.with_host(HotPicCrawler.VIDEO_CDN.host)
        case _:
            pass

    if "thumb" not in url.parts:
        return url

    ext = ".mp4" if url.suffix == ".mp4" or "vid" in url.name else ".jpg"
    new_path = url.path.replace("/thumb/", "/")
    return url.with_path(new_path).with_suffix(ext).with_host(HotPicCrawler.CDN.host)
