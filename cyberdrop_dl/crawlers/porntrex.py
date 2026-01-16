from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import extract_kvs_video
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    VIDEO_JS = "div.video-holder script:-soup-contains('var flashvars')"
    NEXT_PAGE = "div#list_videos_videos_pagination li.next"
    USER_NAME = "div.user-name"
    VIDEOS_2 = "div#list_videos_common_videos_list_items a"
    VIDEOS_1 = "div.video-list a.thumb"
    VIDEOS = f"{VIDEOS_1}, {VIDEOS_2}"
    LAST_PAGE = "div.pagination-holder li.page"
    TITLE = "div.headline > h1"
    MODEL_NAME = "div.name > h1"
    ALBUM_TITLE = "div.album-info p.title-video"
    IMAGES = "a[rel=images].item"
    ALBUMS = "div.list-albums a"
    VIDEOS_OR_ALBUMS = f"{VIDEOS}, {ALBUMS}"


TITLE_TRASH = "Free HD ", "Most Relevant ", "New ", "Videos", "Porn", "for:", "New Videos", "Tagged with"
PRIMARY_URL = AbsoluteHttpURL("https://www.porntrex.com")


class PorntrexCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/...",
        "Album": "/albums/...",
        "User": "/members/...",
        "Tag": "/tags/...",
        "Category": "/categories/...",
        "Model": "/models/...",
        "Playlist": "/playlists/...",
        "Search": "/search/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "porntrex"
    DEFAULT_TRIM_URLS: ClassVar[bool] = False

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.name:  # The ending slash is necessary or we get a 404 error
            scrape_item.url = scrape_item.url / ""

        match scrape_item.url.parts[1:]:
            case ["video", video_id, *_]:
                return await self.video(scrape_item, video_id)
            case ["tags" | "categories" | "models" | "playlists" | "search" | "members" as type_, _, *_]:
                return await self.collection(scrape_item, type_)
            case ["albums", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)

        if "This album is a private album" in soup.get_text(strip=True):
            raise ScrapeError(401, "Private album")

        title = css.select_text(soup, Selector.ALBUM_TITLE)
        title = self.create_title(title, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        for _, link in self.iter_tags(soup, Selector.IMAGES):
            await self.direct_file(scrape_item, link)
            scrape_item.add_children()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if not scrape_item.url.name:
            scrape_item.url = scrape_item.url.parent

        canonical_url = PRIMARY_URL / "video" / video_id
        if await self.check_complete_from_referer(canonical_url):
            return

        soup = await self.request_soup(scrape_item.url)
        video = extract_kvs_video(self, soup)
        link = video.url
        scrape_item.url = canonical_url
        custom_filename = self.create_custom_filename(
            video.title, link.suffix, file_id=video.id, resolution=video.resolution
        )
        await self.handle_file(
            canonical_url, scrape_item, link.name, link.suffix, custom_filename=custom_filename, debrid_link=link
        )

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_type: str) -> None:
        soup = await self.request_soup(scrape_item.url)

        if "models" in scrape_item.url.parts:
            title: str = css.select_text(soup, Selector.MODEL_NAME).title()
        elif "members" in scrape_item.url.parts:
            title: str = css.select_text(soup, Selector.USER_NAME)
        elif "latest-updates" in scrape_item.url.parts:
            title: str = "Latest Updates"
        else:
            title = css.select_text(soup, Selector.TITLE)

        for trash in TITLE_TRASH:
            title = title.replace(trash, "").strip()

        collection_type = collection_type.removesuffix("s")
        title, *_ = title.split(",Page")
        title = self.create_title(f"{title} [{collection_type}]")
        scrape_item.setup_as_album(title)
        if last_page_tag := soup.select(Selector.LAST_PAGE):
            last_page = int(last_page_tag[-1].get_text(strip=True))
        else:
            last_page = 1

        for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEOS_OR_ALBUMS):
            self.create_task(self.run(new_scrape_item))

        await self.proccess_additional_pages(scrape_item, last_page)

        if "models" in scrape_item.url.parts:
            # Additional album pages
            await self.proccess_additional_pages(scrape_item, last_page, block_id="list_albums_common_albums_list")

        elif "members" in scrape_item.url.parts:
            albums_url = scrape_item.url / "albums"
            soup = await self.request_soup(albums_url)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.ALBUMS, new_title_part="albums"):
                self.create_task(self.run(new_scrape_item))

    async def proccess_additional_pages(self, scrape_item: ScrapeItem, last_page: int, **kwargs: str) -> None:
        if last_page == 1:
            return
        block_id: str = "list_videos_common_videos_list_norm"
        from_param_name: str = "from"
        search_query: str = ""
        sort_by: str = scrape_item.url.parts[4] if len(scrape_item.url.parts) > 4 else ""
        sort_by = sort_by or scrape_item.url.query.get("sort_by") or "post_date"
        if "search" in scrape_item.url.parts:
            assert len(scrape_item.url.parts) > 3
            search_query = scrape_item.url.parts[3]
            block_id = "list_videos_videos"
        elif "members" in scrape_item.url.parts:
            block_id = "list_videos_uploaded_videos"

        elif "playlists" in scrape_item.url.parts:
            block_id = "playlist_view_playlist_view_dev"
            sort_by = "added2fav_date"

        page_url = scrape_item.url.with_path("/".join(scrape_item.url.parts[1:3])) / ""
        page_url = page_url.with_query(
            mode="async", function="get_block", block_id=block_id, is_private=0, q=search_query, sort_by=sort_by
        )
        if kwargs:
            page_url = page_url.update_query(kwargs)

        if "members" in scrape_item.url.parts:
            from_param_name = "from_uploaded_videos"
        elif "videos" not in page_url.query["block_id"]:
            from_param_name = "from1"

        for page in itertools.count(2):
            if page > last_page:
                break
            page_url = page_url.update_query({from_param_name: page})
            soup = await self.request_soup(page_url)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEOS_OR_ALBUMS):
                self.create_task(self.run(new_scrape_item))
