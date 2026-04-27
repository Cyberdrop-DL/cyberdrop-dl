from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text, parse_url

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    PHOTO = "div#gridphoto > a.photohref"
    VIDEO = "div[id^='vf'] div.mbcontent a"
    NEXT_PAGE = "div.numlist2 a.nmnext"

    PROFILE_GALLERY = "div[id^='pf'] a"
    PROFILE_PLAYLIST = "div.streameventsday.showAll > div#pl > a"
    DATE_JS = "script[type='application/ld+json']:-soup-contains('uploadDate')"
    GALLERY_TITLE = "div#galleryheader > h1"


_PROFILE_URL_PARTS = {
    "pics": ("uploaded-pics", Selector.PROFILE_GALLERY),
    "videos": ("uploaded-videos", Selector.VIDEO),
    "playlists": ("playlists", Selector.PROFILE_PLAYLIST),
}


@dataclasses.dataclass(slots=True)
class Video:
    title: str
    date: str
    best_src: VideoSource
    sources: tuple[VideoSource, ...]


@dataclasses.dataclass(order=True, slots=True)
class VideoSource:
    resolution: Resolution
    fps: float
    url: AbsoluteHttpURL
    name: str
    format: str


class EpornerCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Categories": "/cat/...",
        "Channels": "/channel/...",
        "Pornstar": "/pornstar/...",
        "Profile": "/profile/...",
        "Search": "/search/...",
        "Search Photos": "/search-photos/...",
        "Video": (
            "/<video_name>-<video-id>",
            "/hd-porn/<video_id>",
            "/embed/<video_id>",
        ),
        "Photo": "/photo/...",
        "Gallery": "/gallery/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.eporner.com/")
    DOMAIN: ClassVar[str] = "eporner"
    FOLDER_DOMAIN: ClassVar[str] = "ePorner"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    _RATE_LIMIT: ClassVar[RateLimit] = 2, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [slug, *_] if slug.startswith("video-"):
                video_id = slug.removeprefix("video-")
                return await self.video(scrape_item, video_id)
            case ["hd-porn" | "embed", video_id, *_]:
                return await self.video(scrape_item, video_id)
            case ["cat" | "channel" | "search" | "pornstar" | "tag", *_]:
                return await self.playlist(scrape_item)
            case ["gallery", *_]:
                return await self.gallery(scrape_item)
            case ["profile", username, *_]:
                return await self.profile(scrape_item, username)
            case ["photo", photo_id, *_]:
                return await self.photo(scrape_item, photo_id)
            case ["search-photos", query, *_]:
                return await self.search_photos(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, username: str) -> None:
        canonical_url = self.PRIMARY_URL / "profile" / username
        if canonical_url in scrape_item.parents and "playlist" in scrape_item.url.parts:
            await self.playlist(scrape_item, from_profile=True)

        title = self.create_title(f"{username} [user]")
        scrape_item.setup_as_profile(title)

        parts_to_scrape = {}
        for name, parts in _PROFILE_URL_PARTS.items():
            if any(p in scrape_item.url.parts for p in (name, parts[0])):
                parts_to_scrape = {name: parts}
                break

        scrape_item.url = canonical_url
        parts_to_scrape = parts_to_scrape or _PROFILE_URL_PARTS
        for name, parts in parts_to_scrape.items():
            part, selector = parts
            url = canonical_url / part
            async for soup in self.web_pager(url):
                for _, new_scrape_item in self.iter_children(scrape_item, soup, selector, new_title_part=name):
                    self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, from_profile: bool = False) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title and not from_profile:
                title = css.select_text(soup, "title")
                title_trash = "Porn Star Videos", "Porn Videos", "Videos -", "EPORNER"
                for trash in title_trash:
                    title = title.rsplit(trash)[0].strip()
                title = self.create_title(title)
                scrape_item.setup_as_album(title)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEO):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                title = css.select_text(soup, Selector.GALLERY_TITLE)
                title = self.create_title(title)
                scrape_item.setup_as_album(title)

            for thumb, new_scrape_item in self.iter_children(scrape_item, soup, Selector.PROFILE_GALLERY):
                assert thumb
                filename = thumb.name.rsplit("-", 1)[0]
                filename, ext = self.get_filename_and_ext(f"{filename}{thumb.suffix}")
                link = thumb.with_name(filename)
                await self.handle_file(link, new_scrape_item, filename, ext)

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem, photo_id: str) -> None:
        canonical_url = self.PRIMARY_URL / "photo" / photo_id
        if await self.check_complete_from_referer(canonical_url):
            return

        soup = await self.request_soup(scrape_item.url)

        scrape_item.url = canonical_url
        link_str = css.select(soup, Selector.PHOTO, "href")
        link = self.parse_url(link_str)
        filename, ext = self.get_filename_and_ext(link.name)
        await self.handle_file(link, scrape_item, filename, ext)

    @error_handling_wrapper
    async def search_photos(self, scrape_item: ScrapeItem, query: str) -> None:
        scrape_item.setup_as_album(self.create_title(f"{query} [photo search]"))
        async for soup in self.web_pager(scrape_item.url):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, ".mbphoto2 > a"):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        canonical_url = self.PRIMARY_URL / f"video-{video_id}"
        if await self.check_complete_from_referer(canonical_url):
            return

        video = await self._request_video(canonical_url, video_id)
        scrape_item.url = canonical_url
        src = video.best_src.url
        scrape_item.uploaded_at = self.parse_iso_date(video.date)
        filename = self.create_custom_filename(
            video.title,
            ext := src.suffix,
            file_id=video_id,
            video_codec="h264",
            resolution=video.best_src.resolution,
            fps=video.best_src.fps,
        )

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext,
            custom_filename=filename,
            debrid_link=src,
        )

    async def _request_video(self, url: AbsoluteHttpURL, video_id: str) -> Video:
        html = await self.request_text(url)
        player_hash = _extract_player_hash(html)
        xhr_url = (self.PRIMARY_URL / "xhr/video" / video_id).with_query(
            hash=_encode_hash(player_hash),
            domain=self.PRIMARY_URL.host,
            fallback="false",
            embed="false",
            supportedFormats="hls,h265,vp9,av1,mp4",
        )
        resp: dict[str, Any] = await self.request_json(xhr_url)
        if resp.get("available") is False:
            raise ScrapeError(404, resp.get("message"))

        return _parse_video(html, resp)


def _parse_video(html: str, video: dict[str, Any]) -> Video:

    ld_json = (
        css.select_text(BeautifulSoup(html, "html.parser"), Selector.DATE_JS)
        .encode("raw_unicode_escape")
        .decode("unicode-escape")
    )
    # This may have invalid json. They do not sanitize the description field
    # See: https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/1211

    sources = tuple(_parse_sources(video["sources"]))
    return Video(
        title=extr_text(ld_json, 'name": "', '",'),
        date=extr_text(ld_json, 'uploadDate": "', '"'),
        sources=sources,
        best_src=max(src for src in sources if src.format == "mp4"),
    )


def _parse_sources(sources: dict[str, dict[str, dict[str, Any]]]) -> Generator[VideoSource]:
    for format, formats in sources.items():
        for name, source in formats.items():
            url = parse_url(source["src"])
            if format == "hls":
                resolution = _parse_hls_res(url)
                fps = 0.0

            else:
                resolution = Resolution.parse(source["labelShort"])
                fps = _parse_fps(name)

            yield VideoSource(
                resolution=resolution,
                fps=fps,
                url=url,
                name=name,
                format=format,
            )


def _extract_player_hash(html: str) -> str:
    if "File has been removed due to copyright owner request" in html:
        raise ScrapeError(451)
    if "Video has been deleted" in html:
        raise ScrapeError(410)

    return extr_text(html, "EP.video.player.hash = '", "';")


def _parse_hls_res(url: AbsoluteHttpURL) -> Resolution:
    for part in reversed(url.parts[-2].split(",")):
        try:
            return Resolution.parse(part)
        except ValueError:
            continue
    return Resolution.unknown()


def _parse_fps(name: str) -> float:
    try:
        return float(extr_text(name, "@", "fps"))
    except ValueError:
        return 0.0


def _encode_hash(hex_hash: str) -> str:
    assert len(hex_hash) == 32
    return "".join(_encode_base_36(int(hex_hash[idx : idx + 8], base=16)) for idx in range(0, 32, 8))


def _encode_base_36(number: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""

    while number != 0:
        number, index = divmod(number, 36)
        result = alphabet[index] + result

    return result or "0"
