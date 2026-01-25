from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import env
from cyberdrop_dl.compat import IntEnum
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures import Resolution
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    _DOWNLOADS = "div#hd-porn-dload > div.dloaddivcol"
    _H264 = "span.download-h264 > a"
    _AV1 = "span.download-av1 > a"
    FORMATS = f"{_DOWNLOADS} {_H264},{_DOWNLOADS} {_AV1}"

    PHOTO = "div#gridphoto > a.photohref"
    VIDEO = "div[id^='vf'] div.mbcontent a"
    NEXT_PAGE = "div.numlist2 a.nmnext"

    PROFILE_GALLERY = "div[id^='pf'] a"
    PROFILE_PLAYLIST = "div.streameventsday.showAll > div#pl > a"
    DATE_JS = "main script:-soup-contains('uploadDate')"
    GALLERY_TITLE = "div#galleryheader > h1"


_PROFILE_URL_PARTS = {
    "pics": ("uploaded-pics", Selector.PROFILE_GALLERY),
    "videos": ("uploaded-videos", Selector.VIDEO),
    "playlists": ("playlists", Selector.PROFILE_PLAYLIST),
}


@dataclasses.dataclass(frozen=True, slots=True)
class Video:
    title: str
    date: str
    best_src: VideoSource


class Codec(IntEnum):
    H264 = 0
    AV1 = -1 if env.EPORNER_PREFER_H264 else 1


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class VideoSource:
    resolution: Resolution
    codec: Codec
    size: str
    url: str

    @staticmethod
    def parse(tag: Tag) -> VideoSource:
        link_str: str = css.get_attr(tag, "href")
        name = tag.get_text(strip=True).removeprefix("Download")
        details = name.split("(", 1)[1].removesuffix(")").split(",")
        res, codec, size = [d.strip() for d in details]
        codec = Codec[codec.upper()]
        return VideoSource(Resolution.parse(res), codec, size, link_str)


class EpornerCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Categories": "/cat/...",
        "Channels": "/channel/...",
        "Pornstar": "/pornstar/...",
        "Profile": "/profile/...",
        "Search": "/search/...",
        "Video": ("/<video_name>-<video-id>", "/hd-porn/<video_id>", "/embed/<video_id>"),
        "Photo": "/photo/...",
        "Gallery": "/gallery/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.eporner.com/")
    DOMAIN: ClassVar[str] = "eporner"
    FOLDER_DOMAIN: ClassVar[str] = "ePorner"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [slug, *_] if slug.startswith("video-"):
                video_id = slug.removeprefix("video-")
                return await self.video(scrape_item, video_id)
            case ["hd-porn" | "embed", video_id, *_]:
                return await self.video(scrape_item, video_id)
            case ["cat" | "channel" | "search" | "pornstar", *_]:
                return await self.playlist(scrape_item)
            case ["gallery", *_]:
                return await self.gallery(scrape_item)
            case ["profile", username, *_]:
                return await self.profile(scrape_item, username)
            case ["photo", photo_id, *_]:
                return await self.photo(scrape_item, photo_id)
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
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        canonical_url = self.PRIMARY_URL / f"video-{video_id}"
        if await self.check_complete_from_referer(canonical_url):
            return

        soup = await self.request_soup(scrape_item.url)

        soup_str = soup.get_text()
        if "File has been removed due to copyright owner request" in soup_str:
            raise ScrapeError(451)
        if "Video has been deleted" in soup_str:
            raise ScrapeError(410)

        scrape_item.url = canonical_url
        # TODO: Force utf8 for soup
        video = _parse_video(soup)
        link = self.parse_url(video.best_src.url)
        scrape_item.possible_datetime = self.parse_iso_date(video.date)
        _, ext = self.get_filename_and_ext(link.name)
        filename = self.create_custom_filename(
            video.title,
            ext,
            file_id=video_id,
            resolution=video.best_src.resolution,
            video_codec=video.best_src.codec.name.lower(),
        )
        await self.handle_file(link, scrape_item, video.title, ext, custom_filename=filename)


def _parse_video(soup: BeautifulSoup) -> Video:
    ld_json = css.select_text(soup, Selector.DATE_JS).encode("raw_unicode_escape").decode("unicode-escape")
    # This may have invalid json. They do not sanitize the description field
    # See: https://github.com/jbsparrow/CyberDropDownloader/issues/1211

    formats = [VideoSource.parse(tag) for tag in soup.select(Selector.FORMATS)]

    return Video(
        title=get_text_between(ld_json, 'name": "', '",'),
        date=get_text_between(ld_json, 'uploadDate": "', '"'),
        best_src=max(formats),
    )
