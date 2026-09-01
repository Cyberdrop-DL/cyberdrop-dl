from __future__ import annotations

import dataclasses
import json
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict, final

from cyberdrop_dl.cache import cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterable

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    ALBUM_FROM_PHOTO = "div#thumbSlider > h2 > a"
    ALBUM_TITLE = "h1[class*=photoAlbumTitle]"
    GIF = "div#js-gifToWebm"
    FLASHVARS = "script:-soup-contains-own('var flashvars_')"
    NEXT_PAGE = "li.page_next a"
    PHOTO = "div#photoImageSection img"
    PLAYLIST_TITLE = "h1.playlistTitle"
    PLAYLIST_VIDEOS = "ul#videoPlaylist a.linkVideoThumb"

    GEO_BLOCKED = ".geoBlocked > h1:-soup-contains('page is not available')"
    NO_VIDEO = "section.noVideo"
    REMOVED = "div.removed"


class PornHubCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/album/<album_id>",
        "Channel": "/channel/<name>",
        "Gif": "/gif/<gif_id>",
        "Photo": "/photo/<photo_id>",
        "Playlist": "/playlist/<playlist_id>",
        "Profile": (
            "/user/<name>",
            "/model/<name>",
            "/pornstar/<name>",
        ),
        "Profile videos": (
            "/user/<name>/videos",
            "/model/<name>/videos",
            "/pornstar/<name>/videos",
        ),
        "Profile albums": (
            "/user/<name>/photos",
            "/model/<name>/photos",
            "/pornstar/<name>/photos",
        ),
        "Profile gifs": (
            "/user/<name>/gifs",
            "/model/<name>/gifs",
            "/pornstar/<name>/gifs",
        ),
        "Video": (
            "/embed/<video_id>",
            "/view_video.php?viewkey=<video_id>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.pornhub.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "pornhub"
    FOLDER_DOMAIN: ClassVar[str] = "PornHub"

    def __post_init__(self) -> None:
        self.api: PornHubAPI = PornHubAPI.from_crawler(self)
        self.profile: PornHubProfile = PornHubProfile(self)
        self.update_cookies(
            dict.fromkeys(
                (
                    "age_verified",
                    "accessPH",
                    "accessAgeDisclaimerPH",
                    "accessAgeDisclaimerUK",
                    "expiredEnterModalShown",
                ),
                2,
            )
        )

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["user" | "channel" | "channels" | "model" | "pornstar" as type_, name, *rest]:
                profile = Profile(type_, name)
                await self.profile.fetch(scrape_item, profile, rest)
            case ["album", album_id]:
                await self.album(scrape_item, album_id)
            case ["playlist", playlist_id]:
                await self.playlist(scrape_item, playlist_id)
            case ["photo", photo_id]:
                await self.photo(scrape_item, photo_id)
            case ["gif", gif_id]:
                await self.gif(scrape_item, gif_id)
            case ["embed", video_id]:
                await self.video(scrape_item, video_id)
            case ["view_video.php"] if video_id := scrape_item.url.query.get("viewkey"):
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        album = await self.api.album(album_id)
        scrape_item.setup_as_album(self.create_title(album.name, album.id), album_id=album.id)
        downloaded = await self.get_album_results(album.id)

        async for photo in self.api.album_photos(album.id):
            if self.check_album_results(photo.canonical_url, downloaded):
                continue
            web_url = self.PRIMARY_URL / "photo" / photo.id
            new_item = scrape_item.create_child(web_url)
            self.create_eager_task(self._photo(new_item, photo))
            scrape_item.add_children()

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem, photo_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        src = css.select(soup, Selector.PHOTO, "src")
        album = _extr_album(soup)
        scrape_item.setup_as_album(self.create_title(album.name, album.id), album_id=album.id)
        await self._photo(scrape_item, Photo(photo_id, self.parse_url(src)))

    @error_handling_wrapper
    async def gif(self, scrape_item: ScrapeItem, gif_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        gif = css.select(soup, Selector.GIF)
        attrs = ("data-mp4", "data-fallback", "data-webm")
        src = next(value for attr in attrs if (value := css.attr_or_none(gif, attr)))
        scrape_item.uploaded_at = self.parse_iso_date(_extr_upload_date(soup))
        await self._photo(scrape_item, Photo(gif_id, self.parse_url(src)))

    @error_handling_wrapper
    async def _photo(self, scrape_item: ScrapeItem, photo: Photo) -> None:
        filename, ext = self.get_filename_and_ext(photo.name, assume_ext=".jpg")
        await self.handle_file(
            photo.canonical_url,
            scrape_item,
            photo.original_name,
            ext,
            custom_filename=filename,
            debrid_link=photo.src,
        )

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        title: str = css.select_text(soup, Selector.PLAYLIST_TITLE)
        title = self.create_title(title, playlist_id)
        scrape_item.setup_as_album(f"{title} [playlist]", album_id=playlist_id)
        for new_scrape_item in self.iter_children(scrape_item, soup, Selector.PLAYLIST_VIDEOS):
            self.create_task(self.run(new_scrape_item, check_referer=True))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        embed_url = self.PRIMARY_URL / "embed" / video_id

        if await self.check_complete(embed_url):
            return

        video = await self.api.video(video_id)
        scrape_item.uploaded_at = self.parse_iso_date(video.uploaded)
        src = max(f for f in video.formats if f.format == "hls")
        m3u8, _ = await self.request_m3u8_playlist(self.parse_url(src.url), headers={"Referer": str(video.url)})

        scrape_item.url = video.url
        filename = self.create_custom_filename(video.title, ext := ".mp4", file_id=video_id, resolution=src.resolution)
        await self.handle_file(
            embed_url,
            scrape_item,
            video.title,
            ext,
            custom_filename=filename,
            m3u8=m3u8,
            thumbnail=video.thumb,
        )


@final
class PornHubProfile:
    class Selector(StrEnum):
        NAME = ".topProfileHeader h1[itemprop=name], div.title h1"
        VIDEOS = "div.container a.linkVideoThumb"
        GIFS = "#moreData li.gifLi a"
        ALBUMS = "#moreData.photosAlbumsListing a"

    def __init__(self, crawler: PornHubCrawler) -> None:
        self.crawler = crawler
        self.manager = crawler.manager

    async def fetch(self, scrape_item: ScrapeItem, profile: Profile, rest: list[str]) -> None:
        match rest:
            case ["videos", *_]:
                await self(scrape_item, profile, self.Selector.VIDEOS)
            case ["gifs", *_]:
                await self(scrape_item, profile, self.Selector.GIFS)
            case ["photos", *_]:
                await self(scrape_item, profile, self.Selector.ALBUMS)
            case []:
                await self.dispatch(scrape_item, profile)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def dispatch(self, scrape_item: ScrapeItem, profile: Profile) -> None:
        url = self.crawler.PRIMARY_URL / profile.type / profile.name
        await self._init(scrape_item, profile)

        paths = ("videos",) if "channel" not in profile.type else ("videos", "gifs/public", "photos/public")
        for path in paths:
            new_item = scrape_item.create_child(url / path)
            self.crawler.create_task(self.crawler.run(new_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def __call__(self, scrape_item: ScrapeItem, profile: Profile, selector: PornHubProfile.Selector) -> None:
        await self._init(scrape_item, profile)
        scrape_item.append_folders(selector.name.casefold())
        await self._iter_pages(scrape_item, selector)

    async def _init(self, scrape_item: ScrapeItem, profile: Profile) -> None:
        if profile in scrape_item.markers:
            return

        url = self.crawler.PRIMARY_URL / profile.type / profile.name
        soup = await self.crawler.request_soup(url)
        name = css.select_text(soup, self.Selector.NAME, decompose="span")
        title = self.crawler.create_title(f"{name} [{profile.type.removesuffix('s')}]")
        scrape_item.setup_as_profile(title)
        scrape_item.markers.append(profile)

    async def _iter_pages(self, scrape_item: ScrapeItem, selector: str) -> None:
        async for soup in self.crawler.web_pager(scrape_item.url):
            for new_item in self.crawler.iter_children(scrape_item, soup, selector):
                self.crawler.create_task(self.crawler.run(new_item))


@dataclasses.dataclass(frozen=True, slots=True)
class Profile:
    type: str
    name: str


@dataclasses.dataclass(slots=True, order=True)
class Photo:
    id: str
    src: AbsoluteHttpURL

    name: str = dataclasses.field(init=False)
    original_name: str = dataclasses.field(init=False)
    canonical_url: AbsoluteHttpURL = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.original_name = self.src.name.rpartition(")")[-1]
        self.name = self.original_name.removeprefix("original_")
        self.canonical_url = self.src.with_name(self.name)


@dataclasses.dataclass(order=True, slots=True, frozen=True)
class Album:
    id: str
    name: str


class Media(TypedDict):
    height: int
    width: int
    format: Literal["hls", "mp4"]
    videoUrl: str
    quality: str | int | list[str]


@dataclasses.dataclass(slots=True, order=True, frozen=True)
class Format:
    resolution: Resolution
    format: Literal["hls", "mp4"]
    url: str


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class Video:
    id: str
    title: str
    thumb: str | None
    uploaded: str
    formats: tuple[Format, ...]
    url: AbsoluteHttpURL


class PornHubAPI(API):
    @cached_method(ttl=600)
    async def csrf_token(self) -> str:
        soup = await self.request_soup(self.PRIMARY_URL)
        return css.select(soup, "input[data-token]", "data-token")

    async def album(self, album_id: str) -> Album:
        url = self.PRIMARY_URL / "album" / album_id
        soup = await self.request_soup(url, impersonate="firefox")
        return Album(album_id, name=css.select_text(soup, Selector.ALBUM_TITLE))

    async def album_photos(self, album_id: str) -> AsyncGenerator[Photo]:
        url = self.PRIMARY_URL / "api/v1/album" / album_id / "show_album_json"
        resp: dict[str, Any] = await self.request_json(url.with_query(token=await self.csrf_token()))
        photos: dict[str, dict[str, Any]] = resp["photos"]
        for photo_id, photo in photos.items():
            yield Photo(photo_id, self.parse_url(photo["img_large"]))

    async def video(self, video_id: str) -> Video:
        page_url = self.PRIMARY_URL.joinpath("view_video.php").with_query(viewkey=video_id)
        soup = await self.request_soup(page_url)
        _check_video_is_available(soup)
        flashvars = _extr_flashvars(soup)
        if flashvars.get("video_unavailable_country", "false") != "false":
            raise ScrapeError(HTTPStatus.FORBIDDEN, "Video is geo restricted")

        return Video(
            id=video_id,
            title=flashvars["video_title"],
            thumb=flashvars.get("image_url"),
            formats=tuple(_parse_formats(flashvars["mediaDefinitions"])),
            uploaded=_extr_upload_date(soup),
            url=page_url,
        )


def _extr_album(soup: BeautifulSoup) -> Album:
    album = css.select(soup, Selector.ALBUM_FROM_PHOTO)
    url: str = css.attr(album, "href")
    return Album(id=url.rpartition("/")[-1], name=css.text(album))


def _extr_upload_date(soup: BeautifulSoup) -> str:
    return css.json_ld(soup, "uploadDate")["uploadDate"]


def _extr_flashvars(soup: BeautifulSoup) -> dict[str, Any]:
    flashvars: str = css.select_text(soup, Selector.FLASHVARS)
    payload = extr_text(flashvars, "{", "};").strip()
    return json.loads("{" + payload + "}")


def _parse_formats(medias: Iterable[Media]) -> Generator[Format]:
    for media in medias:
        quality = media["quality"]
        res = None
        if not isinstance(quality, list):
            try:
                quality = int(quality)
            except ValueError:
                pass

            try:
                res = Resolution.parse(quality)
            except ValueError:
                pass

        res = res or Resolution(media["height"], media["width"])

        yield Format(url=media["videoUrl"], format=media["format"], resolution=res)


def _check_video_is_available(soup: BeautifulSoup) -> None:
    if soup.select_one(Selector.NO_VIDEO):
        raise ScrapeError(HTTPStatus.NOT_FOUND)

    page_text = soup.text
    if soup.select_one(Selector.GEO_BLOCKED) or "This content is unavailable in your country" in page_text:
        raise ScrapeError(HTTPStatus.FORBIDDEN, "Video is geo restricted")

    if (
        "Video has been flagged for verification in accordance with our trust and safety policy" in page_text
        or "Video has been removed at the request of" in page_text
    ):
        raise ScrapeError(HTTPStatus.UNAVAILABLE_FOR_LEGAL_REASONS)

    if (
        soup.select_one(Selector.REMOVED)
        or "This video has been removed" in page_text
        or "This video is currently unavailable" in page_text
    ):
        raise ScrapeError(HTTPStatus.GONE)
