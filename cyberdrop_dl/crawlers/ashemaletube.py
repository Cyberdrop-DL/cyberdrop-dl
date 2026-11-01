from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, final

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, URLConfig
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, json_ld
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import remove_trailing_slash

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    PROFILE_VIDEOS = "div.sub-content div.media-item__inner > a[data-video-preview]"
    SEARCH_VIDEOS = "div.main-content div.media-item__inner > a[data-video-preview]"
    USER_NAME = "h1.username"
    PLAYLIST_VIDEOS = "a.playlist-video-item__thumbnail"
    JS_PLAYER = "script:-soup-contains('var playerConfig =')"
    LOGIN_REQUIRED = "div.loginLinks:-soup-contains('To watch this video please')"
    IMAGE_ITEM = ".main-content .imgItem"
    ALBUM_IMAGES = "div.gallery-detail div.thumb"
    TITLE = ".content-title-row h1"
    GALLERY_ALBUM = "div.profile-content div.galItem > a"
    NEXT_PAGE = "a.rightKey"


class CollectionType(StrEnum):
    ALBUM = "album"
    MODEL = "model"
    PLAYLIST = "playlist"
    SEARCH = "search"
    PROFILE = "profile"


MEDIA_SELECTOR_MAP = {
    CollectionType.ALBUM: Selector.ALBUM_IMAGES,
    CollectionType.MODEL: Selector.PROFILE_VIDEOS,
    CollectionType.PLAYLIST: Selector.PLAYLIST_VIDEOS,
    CollectionType.SEARCH: Selector.SEARCH_VIDEOS,
    CollectionType.PROFILE: Selector.ALBUM_IMAGES,
}

TITLE_SELECTOR_MAP = {
    CollectionType.ALBUM: Selector.TITLE,
    CollectionType.MODEL: Selector.USER_NAME,
    CollectionType.PLAYLIST: "h1",
    CollectionType.SEARCH: "h1",
    CollectionType.PROFILE: Selector.USER_NAME,
}

TITLE_TRASH = "Shemale Porn Videos - Trending"
PRIMARY_URL = AbsoluteHttpURL("https://www.ashemaletube.com")


@HTTPConfig(rate_limit=(3, 10), impersonate=True)
@URLConfig(trim=False)
class AShemaleTubeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Playlist": "/playlists/...",
        "Video": "/videos/...",
        "Model": ("/creators/...", "/model/...", "/pornstars/..."),
        "User": "/profiles/...",
    }
    DOMAIN: ClassVar[str] = "ashemaletube"
    FOLDER_DOMAIN: ClassVar[str] = "aShemaleTube"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match remove_trailing_slash(scrape_item.url).parts[1:]:
            case ["videos", video_id, *_]:
                await self.video(scrape_item, video_id)
            case ["playlists", _playlist_id, *_]:
                await self.collection(scrape_item, CollectionType.PLAYLIST)
            case ["search", *_] if "q" in scrape_item.url.query:
                await self.collection(scrape_item, CollectionType.SEARCH)
            case ["images", *_]:
                await self.direct_file(scrape_item, scrape_item.url.with_query(None))
            case ["pics", _id, _slug, *rest]:
                if rest:
                    await self.image(scrape_item)
                else:
                    await self.album(scrape_item)
            case ["creators" | "profiles" | "pornstars" | "model" as _kind, _, *rest]:
                match rest:
                    case ["galleries", *_]:
                        await self.gallery(scrape_item)
                    case _:
                        await self.collection(scrape_item, CollectionType.MODEL)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem) -> None:
        async for soup in self.web_pager(scrape_item.url):
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.GALLERY_ALBUM):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem) -> None:
        name = ""
        async for soup in self.web_pager(scrape_item.url):
            if not name:
                name = self._create_collection_title(soup, CollectionType.ALBUM)
                scrape_item.setup_as_album(name)

            for thumb in soup.select(MEDIA_SELECTOR_MAP[CollectionType.ALBUM]):
                await self._image(scrape_item, thumb)

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_type: CollectionType) -> None:
        collection_title = ""
        async for soup in self.web_pager(scrape_item.url):
            if not collection_title:
                collection_title = self._create_collection_title(soup, collection_type)
                if collection_type == CollectionType.MODEL:
                    scrape_item.setup_as_profile(collection_title)
                else:
                    scrape_item.setup_as_album(collection_title)

            for new_item in self.iter_children(scrape_item, soup, MEDIA_SELECTOR_MAP[collection_type]):
                self.create_task(self.run(new_item))

    def _create_collection_title(self, soup: BeautifulSoup, collection_type: CollectionType) -> str:
        collection_title: str = css.select_text(soup, TITLE_SELECTOR_MAP[collection_type])
        collection_title = collection_title.replace(TITLE_TRASH, "").strip()
        return self.create_title(f"{collection_title} [{collection_type}]")

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        img = css.select(soup, Selector.IMAGE_ITEM)
        src = self.parse_url(css.select(img, ".image-box img", "src")).with_query(None)
        _, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(
            src,
            scrape_item,
            src.name,
            ext,
            custom_filename=self.create_custom_filename(_, ext, file_id=css.attr(img, "data-image-id")),
        )

    @error_handling_wrapper
    async def _image(self, scrape_item: ScrapeItem, img_tag: Tag) -> None:
        if image := img_tag.select_one(".image-box img"):
            link_str: str = css.attr(image, "src")
        else:
            style: str = css.select(img_tag, "a", "style")
            link_str = extr_text(style, "url('", "');")

        url = self.parse_url(link_str).with_query(None)
        filename, ext = self.get_filename_and_ext(url.name)
        custom_filename = self.create_custom_filename(filename, ext, file_id=css.attr(img_tag, "data-image-id"))
        await self.handle_file(url, scrape_item, filename, ext, custom_filename=custom_filename)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        canonical_url = PRIMARY_URL / "videos" / video_id
        if await self.check_complete_from_referer(canonical_url):
            return

        soup = await self.request_soup(scrape_item.url)
        if soup.select_one(Selector.LOGIN_REQUIRED):
            raise ScrapeError(401)

        scrape_item.uploaded_at = json_ld.upload_date(soup, validate={"@type": "VideoObject"})
        title = css.select_text(soup, Selector.TITLE)
        scrape_item.url = canonical_url
        m3u8, info = await self.request_m3u8_playlist(_extr_hls_src(soup))

        await self.handle_file(
            canonical_url,
            scrape_item,
            title,
            ext := ".mp4",
            custom_filename=self.create_custom_filename(title, ext, file_id=video_id, resolution=info.resolution),
            m3u8=m3u8,
        )


def _extr_hls_src(soup: BeautifulSoup) -> AbsoluteHttpURL:
    player = css.select_text(soup, Selector.JS_PLAYER)
    sources = extr_text(player, "sources: ", "aspectRatio").strip().strip(",")
    sources_data = json.loads(sources)
    return AShemaleTubeCrawler.parse_url(sources_data["hlsAuto"])
